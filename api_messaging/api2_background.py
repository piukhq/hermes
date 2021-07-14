from history.utils import user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from rest_framework.generics import get_object_or_404
from ubiquity.views import AutoLinkOnCreationMixin
from ubiquity.models import PaymentCardAccountEntry
from ubiquity.tasks import deleted_payment_card_cleanup
from user.models import CustomUser


def add_payment_card(message: dict):
    # Auto link if set to True
    # Calls Metis to enrol payment card

    bundle_id = message.get("channel_id")
    payment_card_account = PaymentCardAccount.objects.get(pk=message.get("payment_account_id"))
    user = CustomUser.objects.get(pk=message.get("user_id"))

    if message.get("auto_link"):
        AutoLinkOnCreationMixin.auto_link_to_membership_cards(
            user, payment_card_account, bundle_id, just_created=True
        )

    metis.enrol_new_payment_card(payment_card_account)


def delete_payment_account(message: dict):

    query = {"user_id": message['user_id'],
             "payment_card_account_id": message['payment_card_account_id']}

    get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()
    # 404s shouldn't be happening as would be caught by Angelia. This would likely be caused if a
    # payment card account and/or pca/user combo did not exist but for some reason the corresponding
    # PCAUserAssociation object did (as this is what Angelia checks, not the PCA itself).

    # TODO: Does this 404 need try/catching?

    deleted_payment_card_cleanup(payment_card_id=message['payment_card_account_id'],
                                 payment_card_hash=None,
                                 history_kwargs={"user_info": user_info(user_id=message['user_id'],
                                                                        channel=message['channel'])})
