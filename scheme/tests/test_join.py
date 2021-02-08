from history.utils import GlobalMockAPITestCase
from scheme import credentials
from scheme.models import (
    Category,
    Scheme,
    SchemeCredentialQuestion,
    SchemeAccount,
    SchemeAccountCredentialAnswer,
    SchemeBundleAssociation,
)
from ubiquity.models import SchemeAccountEntry
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.views import MembershipCardView
from user.models import CustomUser, Organisation, ClientApplication, ClientApplicationBundle


class TestJoinExisting(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.join_email = "new_joiner@bink.com"

        SchemeAccountEntry.objects.all().delete()

        category = Category.objects.create()
        cls.scheme = Scheme.objects.create(tier=Scheme.PLL, category=category, slug="fatface")
        question = SchemeCredentialQuestion.objects.create(
            scheme=cls.scheme, type=credentials.EMAIL, manual_question=True, label="Email"
        )
        SchemeCredentialQuestion.objects.create(scheme=cls.scheme, type=credentials.FIRST_NAME, label="First name")
        SchemeCredentialQuestion.objects.create(scheme=cls.scheme, type=credentials.LAST_NAME, label="Last name")

        organisation = Organisation.objects.create(name="test_organisation")
        cls.client_app = ClientApplication.objects.create(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundle.objects.create(bundle_id="test.auth.fake", client=cls.client_app)

        SchemeBundleAssociation.objects.create(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.old_user = CustomUser.objects.create_user("existing_user@bink.com", "Password01")
        cls.old_user.client = cls.client_app
        cls.old_user.external_id = cls.old_user.email
        cls.old_user.save()
        cls.new_user = CustomUser.objects.create_user(cls.join_email, "Password02")
        cls.new_user.client = cls.client_app
        cls.new_user.external_id = cls.new_user.email
        cls.new_user.save()

        cls.scheme_account = SchemeAccount.objects.create(scheme=cls.scheme, order=0)
        SchemeAccountCredentialAnswer.objects.create(
            question=question, scheme_account=cls.scheme_account, answer=cls.join_email
        )

        SchemeAccountEntry.objects.create(user=cls.old_user, scheme_account=cls.scheme_account)

        cls.auth_headers = {
            "HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.old_user, cls.bundle.bundle_id))
        }

    @staticmethod
    def _get_auth_header(user, bundle_id):
        token = GenerateJWToken(
            user.client.organisation.name, user.client.secret, bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    def test_join_existing_account(self):
        """Joining an existing account on a new user causes a link to be set up"""
        MembershipCardView._handle_create_join_route(
            self.new_user,
            None,
            self.scheme,
            {"email": self.join_email, "first_name": "test", "last_name": "user"},
            False
        )

        entries = SchemeAccountEntry.objects.all()
        self.assertEqual(len(entries), 2)
        self.assertSetEqual({e.user for e in entries}, {self.old_user, self.new_user})

    def test_join_same_user_twice(self):
        """Joining an existing account on the same user causes a link to be set up"""
        MembershipCardView._handle_create_join_route(
            self.old_user,
            None,
            self.scheme,
            {"email": self.join_email, "first_name": "test", "last_name": "user"},
            False
        )

        entries = SchemeAccountEntry.objects.all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries.first().user, self.old_user)
