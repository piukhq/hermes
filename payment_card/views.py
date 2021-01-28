import csv
import json
from io import StringIO

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from history.utils import history_bulk_update
from payment_card import metis, serializers
from payment_card.forms import CSVUploadForm
from payment_card.models import PaymentCard, PaymentCardAccount, PaymentCardAccountImage, ProviderStatusMapping
from payment_card.serializers import PaymentCardClientSerializer
from periodic_retry.models import RetryTaskList, PeriodicRetryStatus
from periodic_retry.tasks import PeriodicRetryHandler
from prometheus.metrics import payment_card_status_change_counter, payment_card_processing_seconds_histogram
from rest_framework import generics, serializers as rest_framework_serializers, status
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from scheme.models import Scheme
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry, PaymentCardSchemeEntry, VopActivation
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
from user.models import ClientApplication, Organisation


class ListPaymentCard(generics.ListAPIView):
    """
    List of supported payment cards.
    """
    queryset = PaymentCard.objects
    serializer_class = serializers.PaymentCardSerializer


class PaymentCardAccountQuery(APIView):
    authentication_classes = (ServiceAuthentication,)

    def get(self, request):
        try:
            queryset = PaymentCardAccount.objects.filter(**dict(request.query_params.items()))
        except Exception as e:
            response = {
                'exception_class': e.__class__.__name__,
                'exception_args': e.args
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.QueryPaymentCardAccountSerializer(instance=queryset, many=True)
        return Response(serializer.data)


class RetrievePaymentCardAccount(RetrieveUpdateDestroyAPIView):
    """
    Retrieve and update payment card information.
    """
    queryset = PaymentCardAccount.objects
    serializer_class = serializers.PaymentCardAccountSerializer

    def get_queryset(self):
        user_id = self.request.user.id
        return self.queryset.filter(user_set__id=user_id)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = serializers.UpdatePaymentCardAccountSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Marks a paymentcardaccount as deleted.
        Responds with a 204 - No content.
        ---
        omit_serializer: True
        """
        instance = self.get_object()
        PaymentCardAccountEntry.objects.get(payment_card_account=instance, user__id=request.user.id).delete()

        if instance.user_set.count() < 1:
            instance.is_deleted = True
            instance.save(update_fields=["is_deleted"])
            PaymentCardSchemeEntry.objects.filter(payment_card_account=instance).delete()

            metis.delete_payment_card(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListCreatePaymentCardAccount(APIView):
    serializer_class = serializers.PaymentCardAccountSerializer

    def get(self, request):
        """List payment card accounts
        ---
        response_serializer: serializers.PaymentCardAccountSerializer
        """
        accounts = [self.serializer_class(instance=account).data for account in
                    PaymentCardAccount.objects.filter(user_set__id=request.user.id)]
        return Response(accounts, status=200)

    # TODO: this will be removed later when we remove all the legacy endpoints,
    #  for now commented out as the new payment card creation logic does not work anymore with it
    # def post(self, request):
    #     """Add a payment card account
    #     ---
    #     request_serializer: serializers.PaymentCardAccountSerializer
    #     response_serializer: serializers.PaymentCardAccountSerializer
    #     responseMessages:
    #         - code: 400
    #           message: Error code 400 is indicative of serializer errors.
    #           The error response will show more information.
    #         - code: 403
    #           message: A payment card account by that fingerprint and expiry already exists.
    #     """
    #     status_code, account = self.create_payment_card_account(request.data, request.user)
    #     message = serializers.PaymentCardAccountSerializer(instance=account).data
    #     return Response(message, status=status_code)

    def create_payment_card_account(self, data, user, old_account=None):
        data['psp_token'] = data.pop('token')
        account = PaymentCardAccount(**data)
        result = self._create_payment_card_account(account, user, old_account)
        if not isinstance(result, PaymentCardAccount):
            return result
        else:
            account = result

        self.apply_barclays_images(account)
        return account

    @staticmethod
    def _create_payment_card_account(new_acc, user, old_account):
        if old_account is not None:
            return ListCreatePaymentCardAccount.supercede_old_account(new_acc, old_account, user)

        new_acc.save()
        PaymentCardAccountEntry.objects.create(user=user, payment_card_account=new_acc)
        metis.enrol_new_payment_card(new_acc)

        return new_acc

    @staticmethod
    def supercede_old_account(new_account, old_account, user):
        new_account.token = old_account.token
        new_account.psp_token = old_account.psp_token

        if old_account.is_deleted:
            new_account.save()
            metis.enrol_existing_payment_card(new_account)

        else:
            new_account.status = old_account.status
            new_account.save()

        PaymentCardAccountEntry.objects.create(user=user, payment_card_account=new_account)
        return new_account

    @staticmethod
    def apply_barclays_images(account):
        # if the card is a barclaycard, attach relevant placeholder images to signify that we can't auto-collect.
        if account.pan_start in settings.BARCLAYS_BINS:
            barclays_offer_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                       image_type_code=6)
            barclays_offer_image.payment_card_accounts.add(account)

            try:
                barclays_hero_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                          image_type_code=0,
                                                                          payment_card=account.payment_card)
            except PaymentCardAccountImage.DoesNotExist:
                # not a barclays card that we have an image for, so don't add it.
                pass
            else:
                barclays_hero_image.payment_card_accounts.add(account)


class RetrievePaymentCardSchemeAccounts(generics.ListAPIView):
    serializer_class = serializers.PaymentCardSchemeAccountSerializer

    # TODO: Remove JwtAuthentication before pushing to production.
    authentication_classes = (JwtAuthentication, ServiceAuthentication)

    def get_queryset(self):
        token = self.kwargs.get('token')
        payment_card_account = PaymentCardAccount.objects.filter(token=token).first()
        scheme_account_set = payment_card_account.scheme_account_set.all()

        return [
            {
                'scheme_id': scheme.scheme_id,
                'scheme_account_id': scheme.id
            }
            for scheme in list(scheme_account_set)
        ]


class RetrieveLoyaltyID(APIView):
    authentication_classes = (ServiceAuthentication,)

    def post(self, request, scheme_slug):
        response_data = []
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card_entry = PaymentCardAccountEntry.objects.filter(
                payment_card_account__token=payment_card_token).first()
            if payment_card_entry:
                payment_card = payment_card_entry.payment_card_account
                try:
                    scheme_account_entry = SchemeAccountEntry.objects.get(user=payment_card_entry.user,
                                                                          scheme_account__scheme=scheme)
                except ObjectDoesNotExist:
                    # the user was matched but is not registered in that scheme
                    response_data.append({payment_card_token: None})
                else:
                    scheme_account = scheme_account_entry.scheme_account
                    response_data.append({
                        payment_card.token: scheme_account.third_party_identifier,
                        'scheme_account_id': scheme_account.id
                    })
            else:
                response_data.append({payment_card_token: None})
        return JsonResponse(response_data, safe=False)


class RetrievePaymentCardUserInfo(APIView):
    authentication_classes = (ServiceAuthentication,)

    @staticmethod
    def post(request, scheme_slug):
        response_data = {}
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card_entries = PaymentCardAccountEntry.objects.filter(
                payment_card_account__token=payment_card_token)

            # if there's no payment card for this token, leave it out of the returned data.
            if not payment_card_entries.exists():
                continue

            active_links = PaymentCardSchemeEntry.objects.filter(
                active_link=True,
                scheme_account__scheme=scheme,
                payment_card_account__id__in=(p.payment_card_account.id for p in payment_card_entries)
            )

            if active_links.exists():
                scheme_account = active_links.order_by('scheme_account__created').first().scheme_account
                user_id = scheme_account.get_transaction_matching_user_id()

                response_data[payment_card_token] = {
                    'loyalty_id': scheme_account.third_party_identifier,
                    'scheme_account_id': scheme_account.id,
                    'user_id': user_id,
                    'credentials': scheme_account.credentials()
                }
            else:
                # the user was matched but is not registered in that scheme
                response_data[payment_card_token] = {
                    'loyalty_id': None,
                    'scheme_account_id': None,
                    'user_id': payment_card_entries.first().user.id,
                    'credentials': '',
                }

            active_card = next(
                (x for x in payment_card_entries if x.payment_card_account.status == PaymentCardAccount.ACTIVE), None)
            if active_card:
                response_data[payment_card_token]['card_information'] = {
                    'first_six': active_card.payment_card_account.pan_start,
                    'last_four': active_card.payment_card_account.pan_end
                }

        return JsonResponse(response_data, safe=False)


class UpdatePaymentCardAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = serializers.PaymentCardAccountStatusSerializer

    def _new_retry(self, retry_task, attempts, card_id, retry_status, response_message, response_status):
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'payment_card.metis', retry_task,
            context={"card_id": int(card_id)},
            retry_kwargs={"max_retry_attempts": attempts,
                          "results": [{"caused_by": response_message, "status": response_status}],
                          "status": retry_status
                          }
        )

    def _process_retries(self, retry_task, response_state, retry_id, response_message, response_status, card_id):
        if retry_id is None or retry_id < 1:
            # First time call back
            if response_state == "Retry":
                self._new_retry(retry_task, 100, card_id,
                                PeriodicRetryStatus.REQUIRED, response_message, response_status)
            elif response_state == "Failed":
                # Just save retry info for manual retry without invoking retry attempt
                self._new_retry(retry_task, 0, card_id,
                                PeriodicRetryStatus.FAILED, response_message, response_status)
        else:
            # We are actively retrying
            task = PeriodicRetryHandler.get_task(retry_id=retry_id)
            if response_state == "Retry":
                task.results += [{"retry_message": response_message, "retry_status": response_status}]
                task.status = PeriodicRetryStatus.REQUIRED
                task.save()
            elif response_state == "Failed":
                task.results += [{"retry_message": response_message, "retry_status": response_status}]
                task.status = PeriodicRetryStatus.FAILED
                task.save()
            elif response_state == "Success":
                task.status = PeriodicRetryStatus.SUCCESSFUL
                task.save()

    def put(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        Parameters returned from Enroll and Un-enroll are used to set card status or update retry mechanism
        Currently for VOP also has optional parameters to register deactivations made during unenrol:

        For backward compatibility all parameters are optional and may not be present or set to null
        Note - activations and deactivations do not call back the response is received in the call request
        and there is a different definition of returned parameters note the term "response_status" is used to return
        the same as the response_state below and agent_response_code is used to return response_status

        'id', id of payment card
        'status':  Defaults to zero. Only present on Add call back to set card status
        'response_action': Default is Add otherwise may be "Add" or "Delete"  - note spelling and case
        'response_status': PSP response status examples are "Add:SUCCESS", "Delete:SUCCESS", f"Add:{error_code}"
        'response_state' : "Success", "Retry" or  "Failed"  - note must match spelling and case
        'response_message': Message from VOP explaining request success or reason for failure. Has a ";" to
                            separate general message from any message detail which may be given
        'retry_id':  Id of retry task -1 if not retried and no associated task
        'token': Optional for backward compatibility
        "deactivated_list": List of ids of associated deactivations so as to set the new status in the activations table
        "deactivate_errors": Dict of deactivation errors for reporting in retry task
        "agent_card_uid": Returned when the agent receives a card identity during an add request - saved in agent data
                        for reference
        """
        agent_data = {}
        card_id = request.data.get('id', None)
        token = request.data.get('token', None)
        response_status = request.data.get('response_status', None)
        response_message = request.data.get('response_message', None)
        response_state = request.data.get('response_state', None)
        retry_id = request.data.get('retry_id', None)
        response_action = request.data.get('response_action', "Add")
        new_status_code = request.data.get('status', None)
        deactivated_list = request.data.get('deactivated_list', [])
        deactivate_errors = request.data.get('deactivate_errors', {})
        agent_card_uid = request.data.get('agent_card_uid', None)

        if agent_card_uid:
            agent_data['card_uid'] = agent_card_uid

        if new_status_code is not None:
            new_status_code = int(new_status_code)

        if not (card_id or token):
            raise rest_framework_serializers.ValidationError('No ID or token provided.')

        if card_id:
            payment_card_account = get_object_or_404(PaymentCardAccount, id=int(card_id))
        else:
            payment_card_account = get_object_or_404(PaymentCardAccount, token=token)

        if agent_data:
            payment_card_account.agent_data = agent_data

        if response_action == "Delete":
            # Retry with delete action is only called for providers which support it eg VOP path
            retry_task = "retry_delete_payment_card"
            deactivated_list = request.data.get('deactivated_list', [])
            deactivate_errors = request.data.get('deactivate_errors', {})
            if deactivate_errors:
                response_message = ";".join([response_message, "Deactivation Errors", str(deactivate_errors)])

            if deactivated_list:
                updated_activations = []
                for activation in VopActivation.objects.filter(id__in=deactivated_list).all():
                    activation.status = VopActivation.DEACTIVATED
                    updated_activations.append(activation)

                history_bulk_update(VopActivation, updated_activations, update_fields=["status"])

            self._process_retries(retry_task, response_state, retry_id, response_message, response_status, card_id)

            return Response({
                'id': payment_card_account.id
            })

        return self._add_response(payment_card_account, new_status_code, response_state, retry_id,
                                  response_message, response_status, card_id)

    def _add_response(self, payment_card_account, new_status_code, response_state, retry_id,
                      response_message, response_status, card_id):
        # Normal enrol path for set status
        retry_task = "retry_enrol"

        if new_status_code not in [status_code[0] for status_code in PaymentCardAccount.STATUSES]:
            raise rest_framework_serializers.ValidationError('Invalid status code sent.')

        if new_status_code != payment_card_account.status:
            if payment_card_account.status == PaymentCardAccount.PENDING:
                activation_time = timezone.now() - payment_card_account.updated
                payment_card_processing_seconds_histogram.labels(
                    provider=payment_card_account.payment_card.system_name
                ).observe(activation_time.total_seconds())

            payment_card_account.status = new_status_code
            payment_card_account.save(update_fields=["status", "agent_data"])

            payment_card_status_change_counter.labels(
                provider=payment_card_account.payment_card.system_name,
                status=payment_card_account.status_name
            ).inc()

            # Update soft link status
            if new_status_code == payment_card_account.ACTIVE:
                # make any soft links active for payment_card_account
                PaymentCardSchemeEntry.update_soft_links({'payment_card_account': payment_card_account})

        if response_state:
            # Only metis agents which send a response state will be retried
            self._process_retries(retry_task, response_state, retry_id, response_message, response_status, card_id)

        return Response({
            'id': payment_card_account.id,
            'status': new_status_code
        })


class ListProviderStatusMappings(generics.ListAPIView):
    """
    List available provider-bink status mappings.
    """
    authentication_classes = (ServiceAuthentication,)
    serializer_class = serializers.ProviderStatusMappingSerializer

    def get_queryset(self):
        slug = self.kwargs['slug']

        # we need to provide callers with the UNKNOWN error code for any error not in the returned dictionary.
        # look for an UNKNOWN status card for this provider...
        if not ProviderStatusMapping.objects.filter(provider__slug=slug,
                                                    bink_status_code=PaymentCardAccount.UNKNOWN).exists():
            # there isn't one yet, so add it.
            ProviderStatusMapping(provider=PaymentCard.objects.get(slug=slug),
                                  provider_status_code='BINK_UNKNOWN',
                                  bink_status_code=PaymentCardAccount.UNKNOWN).save()

        return ProviderStatusMapping.objects.filter(provider__slug=slug)


def csv_upload(request):
    # If we had a POST then get the request post values.
    form = CSVUploadForm()
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            payment_card = PaymentCard.objects.get(id=int(request.POST['scheme']))
            uploaded_file = StringIO(request.FILES['emails'].file.read().decode())
            # 6 = magic number for personal offers
            image_instance = PaymentCardAccountImage(payment_card=payment_card, start_date=timezone.now(),
                                                     image_type_code=6, order=0)
            image_instance.save()
            csvreader = csv.reader(uploaded_file, delimiter=',', quotechar='"')
            for row in csvreader:
                for email in row:
                    payment_card_account_entry = PaymentCardAccountEntry.objects.filter(
                        user__email=email.lstrip(),
                        payment_card_account__payment_card=payment_card)
                    if payment_card_account_entry:
                        image_instance.payment_card_accounts.add(
                            payment_card_account_entry.first().payment_card_account
                        )
                    else:
                        image_instance.delete()
                        return HttpResponseBadRequest()

            image_instance.save()

            return redirect('/admin/payment_card/paymentaccountimage/{}'.format(image_instance.id))

    context = {'form': form}
    return render(request, 'admin/csv_upload_form.html', context)


class AuthTransactionView(generics.CreateAPIView):
    authentication_classes = (ServiceAuthentication,)
    permission_classes = (AllowService,)
    serializer_class = serializers.AuthTransactionSerializer


class ListPaymentCardClientApplication(generics.ListAPIView):
    authentication_classes = (ServiceAuthentication,)
    permission_classes = (AllowService,)
    serializer_class = PaymentCardClientSerializer

    def get_queryset(self):
        clients = []
        for system in PaymentCard.SYSTEMS:
            try:
                organisation = Organisation.objects.get(name=system[1])
                client = ClientApplication.objects.get(organisation=organisation, name__contains='Auth Transactions')
                clients.append(client)
            except (Organisation.DoesNotExist, ClientApplication.DoesNotExist):
                pass

        return clients
