import logging

import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.exceptions import APIException
from tenacity import retry, stop_after_attempt, retry_if_exception_type, wait_exponential

from hermes.settings import SPREEDLY_ENVIRONMENT_KEY, SPREEDLY_ACCESS_SECRET, SPREEDLY_GATEWAY_TOKEN, SPREEDLY_BASE_URL
from hermes.tasks import RetryTaskStore
from payment_card.models import PaymentAudit, PaymentStatus, PaymentCardAccount
from scheme.models import SchemeAccount


class PaymentError(APIException):
    status_code = 500
    default_detail = 'Error in Payment processing.'
    default_code = 'payment_error'


@receiver(post_save, sender=PaymentAudit)
def my_handler(sender, **kwargs):
    # TODO: have some sort of error log (Sentry?) if void attempts reaches a certain number?
    logging.info("Payment Audit of id: {} saved/updated: {}".format(
        kwargs['instance'].pk,
        PaymentStatus(kwargs['instance'].status).name
    ))


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
    provider which, if fails, will be cached using django-redis and retried periodically with celery beat.
    """

    payment_auth_url = "{}/v1/gateways/{gateway_token}/authorize.json"
    payment_void_url = "{}/v1/transactions/{transaction_token}/void.json"

    def __init__(self, audit_obj: PaymentAudit, amount: int = 0, currency_code: str = 'GBP', payment_token: str = None):
        self.audit_obj = audit_obj
        self.amount = amount
        self.currency_code = currency_code
        self.payment_token = payment_token

        self.auth_resp = None
        self.void_resp = None
        self.transaction_token = None

    def _auth(self, payment_token: str = None) -> None:
        p_token = payment_token or self.payment_token

        if not p_token:
            raise PaymentError("No payment token provided")

        payload = {
            "transaction": {
                "payment_method_token": self.payment_token,
                "amount": self.amount,
                "currency_code": self.currency_code,
                "order_id": self.audit_obj.transaction_ref
            }
        }

        try:
            resp = requests.post(
                self.payment_auth_url.format(SPREEDLY_BASE_URL, gateway_token=SPREEDLY_GATEWAY_TOKEN),
                json=payload,
                auth=(SPREEDLY_ENVIRONMENT_KEY, SPREEDLY_ACCESS_SECRET)
            )
            self.auth_resp = resp.json()
            if not self.auth_resp['transaction']['succeeded']:
                message = "Payment authorisation error - response: {}".format(
                    self.auth_resp['transaction']['response']
                )
                logging.error(message)
                raise PaymentError("PSP has responded with unsuccessful auth")

            self.transaction_token = self.auth_resp['transaction']['token']

        except requests.RequestException as e:
            raise PaymentError("Error authorising payment with payment service provider") from e
        except KeyError as e:
            raise PaymentError("Error with auth response format") from e

    def _void(self, transaction_token: str = None) -> None:
        transaction_token = transaction_token or self.transaction_token

        if not transaction_token:
            raise PaymentError("No transaction token provided to void")

        try:
            resp = requests.post(
                self.payment_void_url.format(SPREEDLY_BASE_URL, transaction_token=transaction_token),
                auth=(SPREEDLY_ENVIRONMENT_KEY, SPREEDLY_ACCESS_SECRET)
            )

            self.void_resp = resp.json()
            if not self.void_resp['transaction']['succeeded']:
                message = "Payment void error - response: {}".format(
                    self.void_resp['transaction']['response']
                )
                logging.error(message)
                raise PaymentError("PSP has responded with unsuccessful void")
        except requests.RequestException as e:
            raise PaymentError("Error voiding payment with payment service provider") from e
        except KeyError as e:
            raise PaymentError("Error with void response format") from e

    @staticmethod
    def get_payment_audit(scheme_acc: SchemeAccount):
        statuses_to_update = (PaymentStatus.VOID_REQUIRED, PaymentStatus.AUTHORISED)
        payment_audit_objects = PaymentAudit.objects.filter(scheme_account=scheme_acc,
                                                            status__in=statuses_to_update)
        if payment_audit_objects.count() > 1:
            # TODO: Do something? log an error? attempt to void all?
            pass

        return payment_audit_objects.last()

    @staticmethod
    def process_payment_auth(user_id: int, scheme_acc: SchemeAccount, payment_card_id: int,
                             payment_amount: int = 100) -> None:
        """
        Starts an audit trail and authorises a payment.
        Any failure to authorise a payment will cause the join to fail.
        """
        payment_audit = PaymentAudit.objects.create(user_id=user_id, scheme_account=scheme_acc)

        try:
            Payment.attempt_auth(payment_audit, payment_card_id, payment_amount)
        except PaymentCardAccount.DoesNotExist:
            payment_audit.status = PaymentStatus.AUTH_FAILED
            payment_audit.save()
            raise PaymentError("Provided Payment Card Account id does not exist")

    @staticmethod
    @retry(stop=stop_after_attempt(4),
           retry=retry_if_exception_type(PaymentError),
           wait=wait_exponential(min=2, max=8),
           reraise=True)
    def attempt_auth(payment_audit: PaymentAudit, payment_card_id: int,
                     payment_amount: int = 100) -> None:

        try:
            pcard_account = PaymentCardAccount.objects.get(pk=payment_card_id)
            payment = Payment(audit_obj=payment_audit, amount=payment_amount, payment_token=pcard_account.psp_token)

            payment._auth()

            payment_audit.transaction_token = payment.transaction_token
            payment_audit.status = PaymentStatus.AUTHORISED
            payment_audit.save()
        except PaymentError:
            payment_audit.status = PaymentStatus.AUTH_FAILED
            payment_audit.save()
            raise

    @staticmethod
    def process_payment_void(scheme_acc: SchemeAccount) -> None:
        """
        Attempt to void a transaction linked to a scheme account if transaction is in
        AUTHORISED or VOID_REQUIRED status. If the void fails, 'retry_payment_void_task'
        is placed on the retry_tasks queue
        """
        payment_audit = Payment.get_payment_audit(scheme_acc)
        if not payment_audit:
            return

        try:
            Payment.attempt_void(payment_audit)
        except PaymentError:
            task_store = RetryTaskStore()
            transaction_data = {'scheme_acc_id': scheme_acc.id}
            task_store.set_task('payment_card.tasks', 'retry_payment_void_task', transaction_data)

    @staticmethod
    def attempt_void(payment_audit: PaymentAudit) -> None:
        payment_audit.status = PaymentStatus.VOID_REQUIRED
        payment_audit.save()
        try:
            payment_audit.void_attempts += 1
            Payment(audit_obj=payment_audit)._void(transaction_token=payment_audit.transaction_token)
            payment_audit.transaction_token = None
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
        payment_audit = Payment.get_payment_audit(scheme_acc)
        if not payment_audit:
            return

        if payment_audit.status != PaymentStatus.SUCCESS:
            payment_audit.transaction_token = None
            payment_audit.status = PaymentStatus.SUCCESS
            payment_audit.save()
