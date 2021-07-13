from payment_card import metis
from payment_card.models import PaymentCardAccount
from ubiquity.views import AutoLinkOnCreationMixin
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
