from django.db.models.signals import post_save
from django.dispatch import receiver

from scheme.models import SchemeAccount, SchemeAccountEntry
from ubiquity.models import AccountLinkStatus, PaymentCardSchemeEntry, PllUserAssociation


def check_base_link(scheme_account: SchemeAccount):
    scheme_account_entries = SchemeAccountEntry.objects.filter(scheme_account_id=scheme_account.id)
    if scheme_account_entries.exclude(link_status=AccountLinkStatus.ACTIVE).count() == len(scheme_account_entries):
        # If all active_link are not Active then mark all relating PaymentCardSchemeEntry objects active_link False
        PaymentCardSchemeEntry.objects.filter(scheme_account_id=scheme_account.id).update(active_link=False)


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
        check_base_link(scheme_account=instance.scheme_account)
