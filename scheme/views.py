import csv
import json
import logging
from io import StringIO

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView, UpdateAPIView, get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from hermes.utils import ctx
from history.tasks import join_outcome_event, register_outcome_event
from payment_card.payment import Payment
from prometheus.utils import capture_membership_card_status_change_metric
from scheme.forms import CSVUploadForm
from scheme.mixins import IdentifyCardMixin, SchemeAccountJoinMixin, SwappableSerializerMixin, UpdateCredentialsMixin
from scheme.models import ConsentStatus, Exchange, Scheme, SchemeAccount, SchemeAccountImage, SchemeImage, UserConsent
from scheme.serializers import (
    DeleteCredentialSerializer,
    DonorSchemeSerializer,
    GetSchemeAccountSerializer,
    JoinSerializer,
    QuerySchemeAccountSerializer,
    ReferenceImageSerializer,
    SchemeAccountCredentialsSerializer,
    SchemeAccountIdsSerializer,
    SchemeSerializer,
    StatusSerializer,
    UpdateUserConsentSerializer,
)
from ubiquity.models import AccountLinkStatus, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.tasks import async_join_journey_fetch_balance_and_update_status, send_merchant_metrics_for_link_delete
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin, TransactionSerializer
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
from user.models import CustomUser, UserSetting

logger = logging.getLogger(__name__)


class SchemeAccountQuery(APIView):
    authentication_classes = (ServiceAuthentication,)

    def get(self, request):
        try:
            queryset = SchemeAccount.objects.filter(**dict(request.query_params.items()))
        except Exception as e:
            response = {
                "exception_class": e.__class__.__name__,
                "exception_args": e.args,
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        serializer = QuerySchemeAccountSerializer(instance=queryset, many=True, context={"request": request})
        return Response(serializer.data)


class SchemesList(ListAPIView):
    """
    Retrieve a list of loyalty schemes.
    """

    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    queryset = Scheme.objects
    serializer_class = SchemeSerializer

    def get_queryset(self):
        queryset = Scheme.objects
        query = {}
        return self.request.channels_permit.scheme_query(queryset.filter(**query))


class RetrieveScheme(RetrieveAPIView):
    """
    Retrieve a Loyalty Scheme.
    """

    queryset = Scheme.objects
    serializer_class = SchemeSerializer

    def get_queryset(self):
        queryset = Scheme.objects
        return self.request.channels_permit.scheme_query(queryset)


class RetrieveDeleteAccount(SwappableSerializerMixin, RetrieveAPIView):
    """
    Get, update and delete scheme accounts.
    """

    override_serializer_classes = {
        "GET": GetSchemeAccountSerializer,
        "DELETE": GetSchemeAccountSerializer,
        "OPTIONS": GetSchemeAccountSerializer,
    }

    def get_queryset(self):
        return self.request.channels_permit.scheme_account_query(
            SchemeAccount.objects,
            user_id=self.request.user.id,
            user_filter=True,
        )

    def delete(self, request, *args, **kwargs):
        """
        Marks a users scheme account as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        SchemeAccountEntry.objects.get(scheme_account=instance, user__id=request.user.id).delete()

        if instance.user_set.count() < 1:
            instance.is_deleted = True
            instance.save()

            PaymentCardSchemeEntry.objects.filter(scheme_account=instance).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ServiceDeleteAccount(APIView):
    """
    Marks scheme account as deleted and remove all related scheme account entries.
    Responds with a 204 - No content.
    """

    authentication_classes = (ServiceAuthentication,)

    def delete(self, request, *args, **kwargs):
        scheme_account = get_object_or_404(SchemeAccount, id=kwargs["pk"])

        SchemeAccountEntry.objects.filter(scheme_account=scheme_account).delete()
        PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account).delete()
        scheme_account.is_deleted = True
        scheme_account.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserConsent(UpdateAPIView):
    authentication_classes = (ServiceAuthentication,)
    queryset = UserConsent.objects.all()
    serializer_class = UpdateUserConsentSerializer

    def put(self, request, *args, **kwargs):
        if request.data.get("status") == ConsentStatus.FAILED:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)

            consent = self.get_object()
            consent.delete()
            return Response(serializer.data)
        else:
            return self.update(request, *args, **kwargs)


class CreateJoinSchemeAccount(APIView):
    authentication_classes = (ServiceAuthentication,)

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        ---
        response_serializer: GetSchemeAccountSerializer
        """
        try:
            scheme = Scheme.objects.get(slug=kwargs["scheme_slug"])
        except Scheme.DoesNotExist:
            return Response({"code": 400, "message": "Scheme does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=kwargs["user_id"])
        except CustomUser.DoesNotExist:
            return Response({"code": 400, "message": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        # has the user disabled join cards for this scheme?
        setting = UserSetting.objects.filter(
            user=user,
            setting__scheme=scheme,
            setting__slug="join-{}".format(
                scheme.slug,
            ),
        )
        if setting.exists() and setting.first().value == "0":
            return Response(
                {"code": 200, "message": "User has disabled join cards for this scheme"}, status=status.HTTP_200_OK
            )

        # does the user have an account with the scheme already?
        account = SchemeAccount.objects.filter(scheme=scheme, user_set__id=user.id)
        if account.exists():
            return Response(
                {"code": 200, "message": "User already has an account with this scheme."}, status=status.HTTP_200_OK
            )

        # create a join account.
        account = SchemeAccount(
            scheme=scheme,
            order=0,
        )
        account.save()
        SchemeAccountEntry.objects.create(scheme_account=account, user=user, link_status=AccountLinkStatus.JOIN)

        # serialize the account for the response.
        serializer = GetSchemeAccountSerializer(instance=account, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UpdateSchemeAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = StatusSerializer

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
        ctx.x_azure_ref = request.headers.get("x-azure-ref")
        scheme_account_id = int(kwargs["pk"])
        user_id = int(request.data["user_info"]["bink_user_id"])
        journey = request.data.get("journey")
        new_status_code = int(request.data["status"])
        if new_status_code not in [status_code[0] for status_code in AccountLinkStatus.statuses()]:
            raise serializers.ValidationError("Invalid status code sent.")

        scheme_account = get_object_or_404(SchemeAccount, id=scheme_account_id, is_deleted=False)
        scheme_account_entry = scheme_account.schemeaccountentry_set.get(user_id=user_id)
        previous_status = scheme_account_entry.link_status

        if journey == "join" and previous_status == AccountLinkStatus.ACCOUNT_ALREADY_EXISTS:
            # This prevents midas from setting an account to active when joining with a card that already exists.
            # The attempt to update credentials will set the account to ACCOUNT_ALREADY_EXISTS, but midas will
            # then attempt to set the status to active.
            logger.debug(
                "Cannot change a scheme account with ACCOUNT_ALREADY_EXISTS status to ACTIVE "
                f"during the join journey - SchemeAccount id: {scheme_account.id}"
            )
            return Response({"id": scheme_account.id, "status": previous_status}, status=200)

        self.process_active_accounts(scheme_account, journey, new_status_code, scheme_account_entry.id, request.headers)

        if new_status_code != previous_status:
            self.process_new_status(new_status_code, previous_status, scheme_account_entry, request.headers)

        return Response({"id": scheme_account.id, "status": new_status_code})

    @staticmethod
    def process_new_status(new_status_code, previous_status, scheme_account_entry, headers: dict | None = None):
        update_fields = []

        pending_statuses = (
            AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
            AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS,
            AccountLinkStatus.JOIN_IN_PROGRESS,
            AccountLinkStatus.PENDING,
            AccountLinkStatus.PENDING_MANUAL_CHECK,
        )

        capture_membership_card_status_change_metric(
            scheme_slug=Scheme.get_scheme_slug_by_scheme_id(scheme_account_entry.scheme_account.scheme_id),
            old_status=previous_status,
            new_status=new_status_code,
        )

        scheme_account = scheme_account_entry.scheme_account

        # delete main answer credential if an async join failed
        # todo: do we want to delete the main answer credential if the join fails? Why?
        if (
            previous_status
            in [AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS, AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS]
            and new_status_code != AccountLinkStatus.ACTIVE
        ):
            scheme_account.alt_main_answer = ""
            update_fields.append("alt_main_answer")
            # status event join failed
            if previous_status == AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS:
                join_outcome_event.delay(success=False, scheme_account_entry=scheme_account_entry, headers=headers)
            elif previous_status == AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS:
                register_outcome_event.delay(success=False, scheme_account_entry=scheme_account_entry, headers=headers)

        if new_status_code == AccountLinkStatus.ACTIVE:
            # status event join success
            # if balance is not obtained then previous state has been forced to pending so this
            # test will fail for JOIN_ASYNC_IN_PROGRESS
            # @todo How will join_outcome ever be reported if balance is not obtained?
            if previous_status == AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS:
                join_outcome_event.delay(success=True, scheme_account_entry=scheme_account_entry, headers=headers)
            elif previous_status == AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS:
                register_outcome_event.delay(success=True, scheme_account_entry=scheme_account_entry, headers=headers)

            Payment.process_payment_success(scheme_account)
        elif new_status_code not in pending_statuses:
            Payment.process_payment_void(scheme_account)

        scheme_account_entry.set_link_status(new_status_code)

        if update_fields:
            scheme_account.save(update_fields=update_fields)

    def process_active_accounts(
        self, scheme_account, journey, new_status_code, scheme_account_entry_id, headers: dict | None = None
    ):
        if journey in ["join", "join-with-balance"] and new_status_code == AccountLinkStatus.ACTIVE:
            join_date = timezone.now()
            scheme_account.join_date = join_date
            scheme_account.save(update_fields=["join_date"])

            if journey == "join":
                async_join_journey_fetch_balance_and_update_status.delay(
                    scheme_account.id, scheme_account_entry_id, headers
                )

        elif new_status_code == AccountLinkStatus.ACTIVE and not (scheme_account.link_date or scheme_account.join_date):
            date_time_now = timezone.now()
            scheme_slug = scheme_account.scheme.slug

            scheme_account.link_date = date_time_now
            scheme_account.save(update_fields=["link_date"])

            if scheme_slug in settings.SCHEMES_COLLECTING_METRICS:
                send_merchant_metrics_for_link_delete.delay(
                    scheme_account.id, scheme_slug, date_time_now, "link", headers
                )


class UpdateSchemeAccountTransactions(GenericAPIView, MembershipTransactionsMixin):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = TransactionSerializer

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
        ctx.x_azure_ref = request.headers.get("x-azure-ref")
        scheme_account_id = int(kwargs["pk"])
        transactions = json.loads(request.data)

        scheme_account = get_object_or_404(SchemeAccount, id=scheme_account_id, is_deleted=False)
        logger.info(f"Updating transactions for scheme account (id={scheme_account_id})")

        serializer = self.get_serializer(data=transactions, many=True)
        serializer.is_valid(raise_exception=True)

        scheme_account.transactions = serializer.validated_data
        scheme_account.save(update_fields=["transactions"])

        logger.info(f"Transactions updated for scheme account (id={scheme_account_id})")
        return Response({"id": scheme_account.id, "transactions": serializer.validated_data})


class Pagination(PageNumberPagination):
    page_size = 500


class ActiveSchemeAccountAccounts(ListAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """

    # todo: Do we still use this anywhere? Doesn't really fit into post-TC
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return [
            sae.scheme_account for sae in SchemeAccountEntry.objects.filter(link_status=AccountLinkStatus.ACTIVE).all()
        ]

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SystemActionSchemeAccounts(ListAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """

    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return [
            sae.scheme_account
            for sae in SchemeAccountEntry.objects.filter(
                link_status__in=AccountLinkStatus.system_action_required()
            ).all()
        ]

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SchemeAccountsCredentials(RetrieveAPIView, UpdateCredentialsMixin):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """

    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    serializer_class = SchemeAccountCredentialsSerializer

    def get(self, request, *args, **kwargs):
        try:
            account = self.request.channels_permit.scheme_account_query(
                SchemeAccount.objects,
                user_id=self.request.user.id,
                user_filter=False if request.user.uid == "api_user" else True,
            ).get(**kwargs)
        except SchemeAccount.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        scheme_account_entry = SchemeAccountEntry.objects.get(
            scheme_account=account, user_id=request.query_params["bink_user_id"]
        )

        data = {
            "credentials": scheme_account_entry.credentials(),
            "status_name": scheme_account_entry.status_name,
            "display_status": scheme_account_entry.display_status,
            "scheme": account.scheme.slug,
            "id": account.id,
        }

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        """
        Update / Create credentials for loyalty scheme login
        ---
        """
        account = get_object_or_404(SchemeAccount.objects, id=self.kwargs["pk"])
        credential_answers = request.data

        # TODO: Needs investigating further if this should be fixed on Midas' side
        # Patch for midas sending empty value for merchant_identifier
        if not credential_answers.get("merchant_identifier"):
            credential_answers.pop("merchant_identifier", None)

        user_id = request.headers["bink-user-id"]
        scheme_account_entry = SchemeAccountEntry.objects.get(scheme_account=account, user_id=user_id)

        response = self.update_credentials(
            account, credential_answers, scheme_account_entry, allow_existing_main_answer=False
        )
        scheme_account_entry.update_scheme_account_key_credential_fields()
        return Response(response, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Delete scheme credential answers from a scheme account
        ---
        parameters:
          - name: all
            required: false
            description: boolean, True will delete all scheme credential answers
          - name: keep_card_number
            required: false
            description: boolean, if All is not passed, True will delete all credentials apart from card_number
          - name: property_list
            required: false
            description: list, e.g. ['link_questions'] takes properties from the scheme
          - name: type_list
            required: false
            description: list, e.g. ['username', 'password'] of all credential types to delete
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs["pk"])
        user_id = request.headers["bink-user-id"]
        scheme_account_entry = SchemeAccountEntry.objects.get(scheme_account=scheme_account, user_id=user_id)
        serializer = DeleteCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        answers_to_delete = self.collect_credentials_to_delete(scheme_account_entry, data)
        if type(answers_to_delete) is Response:
            return answers_to_delete

        response_list = [answer.question.type for answer in answers_to_delete]
        response_list.sort()
        for answer in answers_to_delete:
            answer.delete()

        if not response_list:
            return Response({"message": "No answers found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"deleted": str(response_list)}, status=status.HTTP_200_OK)

    def collect_credentials_to_delete(self, scheme_account_entry, request_data):
        credential_list = scheme_account_entry.schemeaccountcredentialanswer_set
        answers_to_delete = set()

        if request_data.get("all"):
            answers_to_delete.update(credential_list.all())
            return answers_to_delete

        elif request_data.get("keep_card_number"):
            card_number = scheme_account_entry.scheme_account.card_number
            if card_number:
                credential_list = credential_list.exclude(answer=card_number)

            answers_to_delete.update(credential_list.all())
            return answers_to_delete

        for credential_property in request_data.get("property_list"):
            try:
                questions = getattr(scheme_account_entry.scheme_account.scheme, credential_property)
                answers_to_delete.update(self.get_answers_from_question_list(scheme_account_entry, questions))
            except AttributeError:
                return self.invalid_data_response(credential_property)

        scheme_account_types = [answer.question.type for answer in credential_list.all()]
        question_list = []
        for answer_type in request_data.get("type_list"):
            if answer_type in scheme_account_types:
                question_list.append(scheme_account_entry.scheme_account.scheme.questions.get(type=answer_type))
            else:
                return self.invalid_data_response(answer_type)

        answers_to_delete.update(self.get_answers_from_question_list(scheme_account_entry, question_list))

        return answers_to_delete

    @staticmethod
    def get_answers_from_question_list(scheme_account_entry, questions):
        answers = []
        for question in questions:
            credential_answer = scheme_account_entry.schemeaccountcredentialanswer_set.get(question=question)
            if credential_answer:
                answers.append(credential_answer)

        return answers

    @staticmethod
    def invalid_data_response(invalid_data):
        message = {"message": "No answers found for: {}. Not deleting any credential answers".format(invalid_data)}
        return Response(message, status=status.HTTP_404_NOT_FOUND)


# TODO: Make this a class based view
# TODO: Better handling of incorrect emails
def csv_upload(request):
    # If we had a POST then get the request post values.
    form = CSVUploadForm()
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            scheme = Scheme.objects.get(id=int(request.POST["scheme"]))
            uploaded_file = StringIO(request.FILES["emails"].file.read().decode())
            image_criteria_instance = SchemeAccountImage(scheme=scheme, start_date=timezone.now())
            image_criteria_instance.save()
            csvreader = csv.reader(uploaded_file, delimiter=",", quotechar='"')
            for row in csvreader:
                for email in row:
                    scheme_account = SchemeAccount.objects.filter(user__email=email.lstrip(), scheme=scheme)
                    if scheme_account:
                        image_criteria_instance.scheme_accounts.add(scheme_account.first())
                    else:
                        image_criteria_instance.delete()
                        return HttpResponseBadRequest()

            return redirect("/admin/scheme/schemeaccountimage/{}".format(image_criteria_instance.id))

    context = {"form": form}
    return render(request, "admin/csv_upload_form.html", context)


class DonorSchemes(APIView):
    # todo: Possibly Deprecated??

    authentication_classes = (ServiceAuthentication,)

    @staticmethod
    def get(request, *args, **kwargs):
        """
        DO NOT USE - SERVICE NOT FOR PUBLIC ACCESS
        ---
        response_serializer: scheme.serializers.DonorSchemeAccountSerializer

        """
        host_scheme = Scheme.objects.get(pk=kwargs["scheme_id"])
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=kwargs["user_id"])
        exchanges = Exchange.objects.filter(host_scheme=host_scheme, donor_scheme__in=scheme_accounts.values("scheme"))
        return_data = []

        for e in exchanges:
            scheme_account = scheme_accounts.get(scheme=e.donor_scheme)
            data = DonorSchemeSerializer(e).data
            data["scheme_account_id"] = scheme_account.id
            return_data.append(data)

        return Response(return_data, status=200)


class ReferenceImages(APIView):
    authentication_classes = (ServiceAuthentication,)

    override_serializer_classes = {
        "GET": ReferenceImageSerializer,
    }

    def get(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        ---
        response_serializer: ReferenceImageSerializer
        """
        # TODO: refactor image types to allow SchemeImage.REFERENCE instead of magic number 5.
        images = SchemeImage.objects.filter(image_type_code=5)
        reference_image_serializer = ReferenceImageSerializer(images, many=True)

        return_data = [{"file": data["image"], "scheme_id": data["scheme"]} for data in reference_image_serializer.data]

        return Response(return_data, status=200)


class IdentifyCard(APIView, IdentifyCardMixin):
    authentication_classes = (JwtAuthentication,)

    def post(self, request, *args, **kwargs):
        """
        Identifies and associates a given card image with a scheme ID.
        ---
        parameters:
          - name: base64img
            required: true
            description: the base64 encoded image to identify
        response_serializer: scheme.serializers.IdentifyCardSerializer
        responseMessages:
          - code: 400
            message: no match
        """
        json = self._get_scheme(request.data["base64img"])

        if json["status"] != "success" or json["reason"] == "no match":
            return Response({"status": "failure", "message": json["reason"]}, status=400)

        return Response({"scheme_id": int(json["scheme_id"])}, status=200)


class Join(SchemeAccountJoinMixin, SwappableSerializerMixin, GenericAPIView):
    override_serializer_classes = {
        "POST": JoinSerializer,
    }

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account,
        Register a new loyalty account on the requested scheme,
        Link the newly created loyalty account with the created scheme account.
        """
        scheme_id = int(kwargs["pk"])
        if not self.request.channels_permit.is_scheme_available(scheme_id):
            raise NotFound("Scheme does not exist.")

        scheme_account = request.data.get("scheme_account")
        scheme = get_object_or_404(Scheme.objects, pk=scheme_id)

        validated_data, serializer, new_scheme_account = SchemeAccountJoinMixin.validate(
            data=request.data,
            scheme_account=scheme_account,
            user=request.user,
            permit=request.channels_permit,
            join_scheme=scheme,
            serializer_class=self.get_serializer_class(),
        )

        message, status_code, _ = self.handle_join_request(
            data=validated_data,
            user=request.user,
            scheme_id=scheme_id,
            scheme_account=new_scheme_account,
            serializer=serializer,
            channel=request.channels_permit.bundle_id,
        )

        return Response(message, status=status_code)
