from django.db import transaction

from ubiquity.models import PaymentCardSchemeEntry


def do_update_active_link_to_false(entry: dict) -> bool:
    try:
        payment_scheme_entry = PaymentCardSchemeEntry.objects.select_for_update().filter(
            id=entry.data["paymentcardschemeentry_id"]
        )

        with transaction.atomic():
            payment_scheme_entry[0].active_link = False
            payment_scheme_entry[0].save(update_fields=["active_link"])

        return True

    except Exception:
        return False
