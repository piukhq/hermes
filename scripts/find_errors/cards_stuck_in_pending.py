from .base_script import BaseScript
from payment_card.models import PaymentCardAccount
from payment_card.metis import enrol_existing_payment_card
from ubiquity.models import PaymentCardAccountEntry
from ..models import Correction

class FindCardsStuckInPending(BaseScript):
    """
    accounts = PaymentCardAccount.all_objects.filter(status=0, created__range=["2020-11-01", "2020-12-16"])
    count = 0
    print(len(accounts))
    for account in accounts:

        if count > 1000:
            break
        if not account.is_deleted:
            users = PaymentCardAccountEntry.objects.filter(payment_card_account=account)
            count += 1
            user_list = [x.user.client.name for x in users]
            print(f"{account.id}, {account.is_deleted}, {account.status_name}, {account.payment_card.name},"
              f" {account.created}, {account.psp_token}, no. users:{len(users)}, {','.join(user_list)}")
        enrol_existing_payment_card(account, False)
    else:
        print(f"{account.id}, Deleted: {account.is_deleted}")

    print(count)
    """
    def script(self):
        accounts = PaymentCardAccount.objects.filter(status=PaymentCardAccount.PENDING)
        for account in accounts:
            self.set_correction(Correction.RETAIN_FIX_ENROLL)
            self.make_correction(str(account.id), {'card_id': account.id, 'payment_token': account.psp_token})
            self.result.append(f"card_id:{account.id}"
                                f"script:{self.correction_title}"
                                f"token: {account.psp_token}")











