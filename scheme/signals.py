from django.db.models.signals import post_save
from django.dispatch import receiver

from scheme.models import SchemeAccount, SchemeAccountEntry
from ubiquity.models import AccountLinkStatus, PaymentCardSchemeEntry, PllUserAssociation


@receiver(post_save, sender=SchemeAccountEntry)
def update_pll_active_link(sender, instance, created, update_fields=None, **kwargs):
    # Checks if status has changed and then update active_link in the PaymentCardSchemeEntry model
    # Should only be active when both cards are active and authorised (PaymentCardAccount, SchemeAccount)
    # and PllUserAssociation state is not inactive and slug set to Ubiquity collision.
    # Json pll_Links fields on Scheme and Payment accounts will be updated on SchemeAccountEntry post save signal
    # see update_pll_links_on_save in ubiquity models
    if not created and update_fields and "link_status" in update_fields:
        # todo: PLL stuff - delete next line when happy with solution
        # PaymentCardSchemeEntry.update_active_link_status({"scheme_account": instance})
        PllUserAssociation.update_user_pll_by_scheme_account(scheme_account=instance.scheme_account)
