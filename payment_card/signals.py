from django.db.models.signals import post_save
from django.dispatch import receiver

from payment_card.models import PaymentCardAccount
from ubiquity.models import PaymentCardSchemeEntry


@receiver(post_save, sender=PaymentCardAccount)
def update_pll_active_link(sender, instance, created, **kwargs):
    # Checks if status has changed and then update active_link in the PaymentCardSchemeEntry model
    # Should only be active when both cards are active and authorised (PaymentCardAccount, SchemeAccount)
    if not created:
        PaymentCardSchemeEntry.update_active_link_status({"payment_card_account": instance})
