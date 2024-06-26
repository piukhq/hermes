from django.db.models.signals import post_save
from django.dispatch import receiver

from payment_card.models import PaymentCardAccount
from ubiquity.models import PllUserAssociation


@receiver(post_save, sender=PaymentCardAccount)
def update_pll_active_link(sender, instance, created, update_fields=None, **kwargs):
    # Checks if status has changed and then update active_link in the PaymentCardSchemeEntry model
    # Should only be active when both cards are active and authorised (PaymentCardAccount, SchemeAccount)
    # and PllUserAssociation state is not inactive/slug = Ubiquity collision.
    # Json pll_Links fields on Scheme and Payment accounts will be updated on SchemeAccountEntry post save signal
    # see update_pll_links_on_save in ubiquity models
    if not created and update_fields and "status" in update_fields:
        # todo: PLL stuff - remove next line when happy - change sender from PaymentCard
        # PaymentCardSchemeEntry.update_active_link_status({"payment_card_account": instance})
        PllUserAssociation.update_user_pll_by_pay_account(payment_card_account=instance)
