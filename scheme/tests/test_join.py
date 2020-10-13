from django.test import TestCase

from scheme.models import (
    Category,
    Scheme,
    SchemeCredentialQuestion,
    SchemeAccount,
    SchemeAccountCredentialAnswer,
    SchemeBundleAssociation,
)
from user.models import CustomUser, Organisation, ClientApplication, ClientApplicationBundle
from ubiquity.models import SchemeAccountEntry
from ubiquity.views import MembershipCardView
from ubiquity.tests.property_token import GenerateJWToken
from scheme import credentials


class TestJoinExisting(TestCase):
    def setUp(self):
        self.join_email = "new_joiner@bink.com"

        SchemeAccountEntry.objects.all().delete()

        category = Category.objects.create()
        self.scheme = Scheme.objects.create(tier=Scheme.PLL, category=category, slug="fatface")
        question = SchemeCredentialQuestion.objects.create(
            scheme=self.scheme, type=credentials.EMAIL, manual_question=True, label="Email"
        )
        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=credentials.FIRST_NAME, label="First name")
        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=credentials.LAST_NAME, label="Last name")

        organisation = Organisation.objects.create(name="test_organisation")
        self.client_app = ClientApplication.objects.create(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        self.bundle = ClientApplicationBundle.objects.create(bundle_id="test.auth.fake", client=self.client_app)

        SchemeBundleAssociation.objects.create(
            scheme=self.scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        self.old_user = CustomUser.objects.create_user("existing_user@bink.com", "Password01")
        self.old_user.client = self.client_app
        self.old_user.external_id = self.old_user.email
        self.old_user.save()
        self.new_user = CustomUser.objects.create_user(self.join_email, "Password02")
        self.new_user.client = self.client_app
        self.new_user.external_id = self.new_user.email
        self.new_user.save()

        self.scheme_account = SchemeAccount.objects.create(scheme=self.scheme, order=0)
        SchemeAccountCredentialAnswer.objects.create(
            question=question, scheme_account=self.scheme_account, answer=self.join_email
        )

        SchemeAccountEntry.objects.create(user=self.old_user, scheme_account=self.scheme_account)

        self.auth_headers = {
            "HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(self.old_user, self.bundle.bundle_id))
        }

    def _get_auth_header(self, user, bundle_id):
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
