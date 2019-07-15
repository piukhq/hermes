import logging
from typing import Optional

import sentry_sdk
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.exceptions import APIException
from tenacity import retry, stop_after_attempt, retry_if_exception_type, wait_exponential

from hermes.settings import SPREEDLY_ENVIRONMENT_KEY, SPREEDLY_ACCESS_SECRET, SPREEDLY_GATEWAY_TOKEN
from hermes.spreedly import Spreedly, SpreedlyError
from hermes.tasks import RetryTaskStore
from payment_card.models import PaymentAudit, PaymentStatus, PaymentCardAccount
from scheme.models import SchemeAccount


class PaymentError(APIException):
    status_code = 500
    default_detail = 'Error in Payment processing.'
    default_code = 'payment_error'


@receiver(post_save, sender=PaymentAudit)
def payment_audit_log_signal_handler(sender, **kwargs):
    payment_audit_instance = kwargs['instance']
    if payment_audit_instance.status == PaymentStatus.VOID_REQUIRED and payment_audit_instance.void_attempts >= 10:
        sentry_sdk.capture_message(
            "Payment Audit of id: {} - Has reached a void retry count of {}".format(
                payment_audit_instance.pk,
                payment_audit_instance.void_attempts
            )
        )

    logging.info("Payment Audit of id: {} saved/updated: {}".format(
        payment_audit_instance.pk,
        PaymentStatus(payment_audit_instance.status).name
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

    def __init__(self, audit_obj: PaymentAudit, amount: Optional[int] = None, currency_code: str = 'GBP',
                 payment_token: Optional[str] = None):
        self.audit_obj = audit_obj
        self.amount = amount
        self.currency_code = currency_code
        self.payment_token = payment_token

        self.spreedly = Spreedly(SPREEDLY_ENVIRONMENT_KEY, SPREEDLY_ACCESS_SECRET, currency_code=currency_code)

    def _auth(self, payment_token: Optional[str] = None) -> None:
        p_token = payment_token or self.payment_token
        if not p_token:
            raise PaymentError("No payment token provided")

        try:
            self.spreedly.authorise(
                payment_token=self.payment_token,
                amount=self.amount,
                order_id=self.audit_obj.transaction_ref,
                gateway_token=SPREEDLY_GATEWAY_TOKEN
            )
        except SpreedlyError as e:
            raise PaymentError from e
        except KeyError as e:
            raise PaymentError("Error with auth response format") from e

    def _void(self, transaction_token: Optional[str] = None) -> None:
        transaction_token = transaction_token or self.spreedly.transaction_token
        if not transaction_token:
            raise PaymentError("No transaction token provided to void")

        try:
            self.spreedly.void(transaction_token)
        except SpreedlyError as e:
            raise PaymentError from e
        except KeyError as e:
            raise PaymentError("Error with void response format") from e

    @staticmethod
    def get_payment_audit(scheme_acc: SchemeAccount) -> PaymentAudit:
        statuses_to_update = (PaymentStatus.VOID_REQUIRED, PaymentStatus.AUTHORISED)
        payment_audit_objects = PaymentAudit.objects.filter(scheme_account=scheme_acc,
                                                            status__in=statuses_to_update)
        return payment_audit_objects.last()

    @staticmethod
    def process_payment_auth(user_id: int, scheme_acc: SchemeAccount, payment_card_id: int,
                             payment_amount: int) -> None:
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
                     payment_amount: int) -> None:
        try:
            pcard_account = PaymentCardAccount.objects.get(pk=payment_card_id)
            payment = Payment(audit_obj=payment_audit, amount=payment_amount, payment_token=pcard_account.psp_token)

            payment._auth()

            payment_audit.transaction_token = payment.spreedly.transaction_token
            payment_audit.status = PaymentStatus.AUTHORISED
            payment_audit.save()
        except PaymentError as e:
            payment_audit.status = PaymentStatus.AUTH_FAILED
            payment_audit.save()
            logging.error(
                "Payment error for SchemeAccount id: {} - PaymentAudit id: {} - Error description: {}".format(
                    payment_audit.scheme_account_id,
                    payment_audit.id,
                    e.detail
                )
            )
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
        except PaymentError as e:
            payment_audit.save()
            logging.error(
                "Payment error for SchemeAccount id: {} - PaymentAudit id: {} - Error description: {}".format(
                    payment_audit.scheme_account_id,
                    payment_audit.id,
                    e.detail
                )
            )
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
