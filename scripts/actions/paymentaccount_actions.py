from payment_card.models import PaymentCardAccount

# from ubiquity.models import PaymentCardAccountEntry


def do_update_hash(entry):
    try:
        acc = PaymentCardAccount.objects.get(id=entry.data["payment_card_account_id"])
        acc.hash = entry.data["new_hash"]
        acc.save(update_fields=["hash", "updated"])
        return True
    except Exception:
        return False


def do_remove_payment_account(entry):
    pass
    """
    try:
        acc = PaymentCardAccount.objects.get(id=entry.data["payment_card_account_id"])
        instance = self.get_object()
        PaymentCardAccountEntry.objects.get(payment_card_account=instance, user__id=request.user.id).delete()

        if instance.user_set.count() < 1:
            instance.is_deleted = True
            instance.save(update_fields=["is_deleted"])
            PaymentCardSchemeEntry.objects.filter(payment_card_account=instance).delete()

            metis.delete_payment_card(instance)

        return True
    except Exception:
        return False
    """
