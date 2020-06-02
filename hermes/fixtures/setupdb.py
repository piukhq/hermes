from hermes.settings import BINK_CLIENT_ID, BINK_BUNDLE_ID
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount, Scheme, SchemeCredentialQuestion
from ubiquity.models import PaymentCardSchemeEntry, SchemeAccountEntry, PaymentCardAccountEntry
from user.models import ClientApplicationBundle, ClientApplication, ClientApplicationKit, CustomUser, Organisation
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory)


def clear_db():
    CustomUser.objects.all().delete()
    ClientApplicationBundle.objects.all().delete()
    ClientApplicationKit.objects.all().delete()
    ClientApplication.objects.all().delete()
    Organisation.objects.all().delete()
    PaymentCardSchemeEntry.objects.all().delete()
    PaymentCardAccount.objects.all().delete()
    SchemeAccount.objects.all().delete()
    SchemeCredentialQuestion.objects.all().delete()
    Scheme.objects.all().delete()


def set_up_db(cls):
    """Test cases have had issues with database of being inconsistent between test classes
        By calling this function the users, bundles and clients are reset to the standard
        defaults
    """
    clear_db()
    cls.bink_client_id = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'
    cls.bink_secret = "This is the Bink Secret Bink Secret this is"
    cls.bink_bundle_id = BINK_BUNDLE_ID
    cls.organisation = OrganisationFactory(pk=1, name='Loyalty Angels')
    cls.bink_client_app = ClientApplicationFactory(pk=BINK_CLIENT_ID, organisation=cls.organisation,
                                                   name='Bink', secret=cls.bink_secret,
                                                   client_id=cls.bink_client_id)
    cls.bink_bundle = ClientApplicationBundleFactory(pk=1, client=cls.bink_client_app,
                                                     bundle_id=cls.bink_bundle_id)
    cls.bink_kit = ClientApplicationKit.objects.create(client_id=cls.bink_client_id,
                                                       kit_name='core', is_valid=True)


def print_db():
    """This is useful to examine certain frequently used tables and setups within a test class
    """
    user_list = CustomUser.objects.all().values()
    print(f"Users  = {CustomUser.objects.count()}:")
    for user in user_list:
        print(f"      {user}")

    app_list = ClientApplicationBundle.objects.all().values()
    print(f"APP Bundles = {ClientApplicationBundle.objects.count()}")
    for app in app_list:
        print(f"      {app}")

    print(f"APP kits = {ClientApplicationKit.objects.count()} {ClientApplicationKit.objects.all().values()}")
    app_list = ClientApplication.objects.all().values()
    print(f"APP = {ClientApplication.objects.count()}")
    for app in app_list:
        print(f"      {app}")
    print(f"Organisations = {Organisation.objects.count()} {Organisation.objects.all().values()}")
    schemes = Scheme.objects.all().values()
    print(f"Schemes = {Scheme.objects.count()}")
    for scheme in schemes:
        print(f"      {scheme}")
    print(f"SchemeAccounts = {SchemeAccount.objects.count()}")
    print(f"PaymentCardAccount = {PaymentCardAccount.objects.count()}")
    print(f"PaymentCardSchemeEntry = {PaymentCardSchemeEntry.objects.count()}")
    print(f"SchemeAccountEntry = {SchemeAccountEntry.objects.count()}")
    print(f"PaymentCardAccountEntry = {PaymentCardAccountEntry.objects.count()}")

    print("-----")
