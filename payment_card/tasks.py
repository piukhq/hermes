import logging

import sentry_sdk

from payment_card.payment import Payment, PaymentError
from scheme.models import SchemeAccount


def payment_void_task(transaction_data: dict) -> (bool, str):
    done = False
    try:
        scheme_acc = SchemeAccount.objects.get(pk=transaction_data['scheme_acc_id'])
        payment_audit = Payment.get_payment_audit(scheme_acc)
        if not payment_audit:
            err_msg = "scheme_account_id: {} - No Payment Audit found".format(transaction_data['scheme_acc_id'])
            logging.error(err_msg)
            # returns done as True to stop further retries
            done = True
            return done, err_msg

        Payment.attempt_void(payment_audit)
        done = True
        return done, "done"
    except PaymentError as e:
        sentry_sdk.capture_exception()
        return done, e.detail
