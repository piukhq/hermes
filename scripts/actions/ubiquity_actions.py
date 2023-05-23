from django.db import transaction

from ubiquity.models import PaymentCardSchemeEntry


def do_update_active_link_to_false(entry: dict) -> bool:
    try:

        with transaction.atomic():
            payment_scheme_entry = PaymentCardSchemeEntry.objects.select_for_update().get(
                id=entry.data["paymentcardschemeentry_id"]
            )
            payment_scheme_entry.active_link = False
            payment_scheme_entry.save(update_fields=["active_link"])

        return True

    except Exception:
        return False
