from collections import defaultdict

from django.db.models import Count

from ..actions.corrections import Correction
from .base_script import BaseScript
from payment_card.models import PaymentCardAccount


class FindDuplicatePaymentCardsWithSameFingerprint(BaseScript):
    def script(self):
        duplicated_fingerprints = (
            PaymentCardAccount.objects.values("fingerprint")
            .annotate(count=Count("fingerprint"))
            .values("fingerprint")
            .order_by()
            .filter(count__gt=1)
        )

        duplicate_payment_card_accounts = (
            PaymentCardAccount.objects.filter(fingerprint__in=duplicated_fingerprints)
            .order_by("-expiry_year", "-expiry_month").all()
        )

        accs_sorted_by_fingerprint = defaultdict(list)
        for payment_account in duplicate_payment_card_accounts:
            accs_sorted_by_fingerprint[payment_account.fingerprint].append(payment_account)

        for fingerprint, sorted_accounts in accs_sorted_by_fingerprint.items():
            accounts_to_delete = []
            # We only want the payment card account with the latest expiry to be the active card
            for account in sorted_accounts[1:]:
                accounts_to_delete.append(account.id)
                data = {
                    "card_id": account.id,
                    "fingerprint": account.fingerprint
                }
                self.make_correction(unique_id_string=f"{account.id}", data=data)
                self.set_correction(Correction.PAYMENT_ACCOUNT_DELETE_AND_VOP_DEACTIVATE)
            self.found += len(accounts_to_delete)
            self.result.append(
                f"Fingerprint: {fingerprint} - Duplicate accounts to delete: {accounts_to_delete}"
            )


