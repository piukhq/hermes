import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.exceptions import APIException

from payment_card.models import PaymentAudit, PaymentStatus, PaymentCardAccount
from payment_card.tasks import RetryTaskStore
from scheme.models import SchemeAccount


class PaymentError(APIException):
    status_code = 503
    default_detail = 'Error in Payment processing.'
    default_code = 'payment_error'


@receiver(post_save, sender=PaymentAudit)
def my_handler(sender, **kwargs):
    # TODO: use logging
    print("Payment Audit saved/updated: {}".format(PaymentStatus(kwargs['instance'].status).name))


class Payment:
    """
    Handles Payment authorisation and void with payment service provider.

    Authorisation and void can be handled with the static methods available:
    - process_payment_auth
    - process_payment_void

    These methods can be called without the need of directly instantiating a class instance.

    PaymentAudit objects will be created automatically to track the state of the payment and will
    contain information of the user and scheme account related to the payment.

    Payments requiring void will result in a call to void the transaction to the payment service
    provider which, if fails, will be cached using django-redis to retry periodically.
    """

    PAYMENT_TOKEN_AUTH_URL = "core.spreedly.com/v1/gateways/D5lARug9NzuUfrFNkbeiWYSdHtx/authorize.json"
    PAYMENT_TOKEN_VOID_URL = "core.spreedly.com/v1/transactions/{transaction_token}/void.json"

    def __init__(self, audit_obj: PaymentAudit, amount: int = 0, currency_code: str = 'GBP', payment_token: str = None):
        self.audit_obj = audit_obj
        self.amount = amount
        self.currency_code = currency_code
        self.payment_token = payment_token

        self.auth_resp = None
        self.void_resp = None
        self.transaction_id = None

    def auth(self, payment_token: str=None) -> None:
        p_token = payment_token or self.payment_token

        if not p_token:
            raise PaymentError("No payment token provided")

        headers = {
            "Authorization": "Basic {}"
        }

        payload = {
            "transaction": {
                "payment_method_token": self.payment_token,
                "amount": self.amount,
                "currency_code": self.currency_code
                # "order_id":
            }
        }

        try:
            # resp = requests.post(self.PAYMENT_TOKEN_AUTH_URL, json=payload, headers=headers)
            # resp.raise_for_status()

            # self.auth_resp = json.dumps(resp.json())
            self.auth_resp = {'transaction_id': 'test_transaction_id-12356'}
            self.transaction_id = self.auth_resp['transaction_id']
            print('Called auth')

        except requests.RequestException as e:
            # TODO: retry for service errors. Check if this should be a synchronous retry.
            raise PaymentError("Error authorising payment with payment service provider") from e

    def void(self, transaction_token: str=None) -> None:
        transaction_token = transaction_token or self.auth_resp['transaction']['token']
        print('Called void')
        if not transaction_token:
            raise PaymentError("No transaction token provided to void")

        url = self.PAYMENT_TOKEN_VOID_URL.format(transaction_token=transaction_token)

        # try:
        #     resp = requests.post(url)
        #     resp.raise_for_status()
        #
        #     self.void_resp = resp.json()
        #     if not self.void_resp['response']['success']:
        #         raise PaymentError('Unsuccessful void response')
        # except requests.RequestException as e:
        #     # TODO: retry for service errors. Should this be async?
        #     raise PaymentError("Error voiding payment with payment service provider") from e
        # except KeyError as e:
        #     raise PaymentError("Unexpected response received when calling void") from e

    @staticmethod
    def _get_payment_audit(scheme_acc: SchemeAccount):
        statuses_to_update = [PaymentStatus.AUTHORISED, PaymentStatus.VOID_REQUIRED]
        payment_audit_objects = PaymentAudit.objects.filter(scheme_account=scheme_acc,
                                                            status__in=statuses_to_update)
        if payment_audit_objects.count() > 1:
            # TODO: Do something? log an error? attempt to void all?
            pass

        return payment_audit_objects.last()

    @staticmethod
    def process_payment_auth(user_id: int, scheme_acc: SchemeAccount, payment_card_id: int, payment_amount: int=100) -> None:
        """
        Starts an audit trail and authorises a payment.
        Any failure to authorise a payment will cause the join to fail.
        """
        payment_audit = PaymentAudit.objects.create(user_id=user_id, scheme_account=scheme_acc)
        try:
            pcard_account = PaymentCardAccount.objects.get(pk=payment_card_id)
            payment = Payment(audit_obj=payment_audit, amount=payment_amount, payment_token=pcard_account.psp_token)

            payment.auth()

            payment_audit.transaction_id = payment.transaction_id
            payment_audit.status = PaymentStatus.AUTHORISED
            payment_audit.save()
        except PaymentCardAccount.DoesNotExist:
            payment_audit.status = PaymentStatus.AUTH_FAILED
            payment_audit.save()
            raise PaymentError('Provided Payment Card Account id does not exist')
        except PaymentError:
            payment_audit.status = PaymentStatus.AUTH_FAILED
            payment_audit.save()
            raise

    @staticmethod
    # TODO: pass in and add filter audit obj by user_id
    def process_payment_void(scheme_acc: SchemeAccount) -> None:
        """
        Attempt to void a transaction linked to a scheme account if transaction is in
        AUTHORISED or VOID_REQUIRED status.
        """
        payment_audit = Payment._get_payment_audit(scheme_acc)
        if not payment_audit:
            return

        try:
            Payment._attempt_void(payment_audit)
        except PaymentError:
            task_store = RetryTaskStore()
            task_store.set_task('payment_card.payment', 'retry_payment_void', {})
            # TODO: retry failed void. async? queue?

    @staticmethod
    def _attempt_void(payment_audit: PaymentAudit) -> None:
        payment_audit.status = PaymentStatus.VOID_REQUIRED
        payment_audit.save()
        try:
            payment_audit.void_attempts += 1
            Payment(audit_obj=payment_audit).void(transaction_token=payment_audit.transaction_id)
            payment_audit.transaction_id = None
            payment_audit.status = PaymentStatus.VOID_SUCCESSFUL
            payment_audit.save()
        except PaymentError:
            payment_audit.save()
            raise

    @staticmethod
    def process_payment_success(scheme_acc: SchemeAccount) -> None:
        """
        Set the PaymentAudit status to Payment.SUCCESS if it isn't already.
        """
        payment_audit = Payment._get_payment_audit(scheme_acc)
        if not payment_audit:
            return

        if payment_audit.status != PaymentStatus.SUCCESS:
            payment_audit.transaction_id = None
            payment_audit.status = PaymentStatus.SUCCESS
            payment_audit.save()
