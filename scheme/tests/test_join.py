from django.test import TestCase
from scheme.models import Category, Scheme, SchemeCredentialQuestion, SchemeAccount, SchemeAccountCredentialAnswer
from user.models import CustomUser
from ubiquity.models import SchemeAccountEntry
from ubiquity.views import MembershipCardView
from scheme import credentials


class TestJoinExisting(TestCase):
    def setUp(self):
        self.join_email = "new_joiner@bink.com"

        SchemeAccountEntry.objects.all().delete()

        self.old_user = CustomUser.objects.create_user("existing_user@bink.com", "Password01")
        self.new_user = CustomUser.objects.create_user(self.join_email, "Password02")

        category = Category.objects.create()
        self.scheme = Scheme.objects.create(tier=Scheme.PLL, category=category, slug="fatface")
        question = SchemeCredentialQuestion.objects.create(
            scheme=self.scheme, type=credentials.EMAIL, manual_question=True
        )
        self.scheme_account = SchemeAccount.objects.create(scheme=self.scheme, order=0)
        SchemeAccountCredentialAnswer.objects.create(
            question=question, scheme_account=self.scheme_account, answer=self.join_email
        )

        SchemeAccountEntry.objects.create(user=self.old_user, scheme_account=self.scheme_account)

    def test_join_existing_account(self):
        """Joining an existing account on a new user causes a link to be set up"""
        MembershipCardView._handle_create_join_route(
            self.new_user, None, self.scheme.id, {"email": self.join_email, "first_name": "test", "last_name": "user"}
        )

        entries = SchemeAccountEntry.objects.all()
        self.assertEqual(len(entries), 2)
        self.assertSetEqual({e.user for e in entries}, {self.old_user, self.new_user})

    def test_join_same_user_twice(self):
        """Joining an existing account on the same user causes a link to be set up"""
        MembershipCardView._handle_create_join_route(
            self.old_user, None, self.scheme.id, {"email": self.join_email, "first_name": "test", "last_name": "user"}
        )

        entries = SchemeAccountEntry.objects.all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries.first().user, self.old_user)
