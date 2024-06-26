import json
from unittest.mock import PropertyMock, patch

import arrow
import jwt
from django.test import Client, override_settings
from django.urls import reverse

from history.utils import GlobalMockAPITestCase
from scheme.models import SchemeBundleAssociation
from scheme.tests.factories import SchemeBundleAssociationFactory, SchemeFactory
from ubiquity import channel_vault
from user.models import ClientApplicationBundle
from user.serializers import MakeMagicLinkSerializer
from user.tests.factories import ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory


class TestMakeMagicLinkViews(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bink_web_secret = "local jwt signing for com.bink.web"
        channel_vault._bundle_secrets = {
            "com.bink.wallet": {"jwt_secret": "local jwt signing for com.bink.wallet"},
            "com.bink.web": {"jwt_secret": cls.bink_web_secret},
        }
        cls.url = "test url"
        cls.lifetime = 90
        cls.BINK_CLIENT_ID = "ffhfhfhfhplqszzccgbnmml987tvgcxznnkn"
        cls.BINK_BUNDLE_ID = "com.bink.web"
        cls.bink_organisation = OrganisationFactory(name="loyalty")
        cls.bink_client_app = ClientApplicationFactory(
            organisation=cls.bink_organisation, name="loyalty client application", client_id=cls.BINK_CLIENT_ID
        )

        cls.bink_bundle = ClientApplicationBundleFactory(
            client=cls.bink_client_app,
            bundle_id=cls.BINK_BUNDLE_ID,
            magic_link_url=cls.url,
            magic_lifetime=cls.lifetime,
            template="path/to/template",
        )
        cls.bink_scheme_active = SchemeFactory()
        cls.bink_scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.bink_scheme_active,
            bundle=cls.bink_bundle,
            status=SchemeBundleAssociation.ACTIVE,
        )

        cls.bink_scheme_inactive = SchemeFactory()
        cls.bink_scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.bink_scheme_inactive,
            bundle=cls.bink_bundle,
            status=SchemeBundleAssociation.INACTIVE,
        )
        cls.client = Client()

    @patch.object(ClientApplicationBundle, "template", new_callable=PropertyMock)
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    def test_view_active_enabled(self, mock_template):
        mock_template.return_value.read.return_value = b"{{ magic_link_url }}"
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1@example.com",
                "slug": self.bink_scheme_active.slug,
                "locale": "en_GB",
                "bundle_id": self.BINK_BUNDLE_ID,
            },
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content, "Successful")

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    def test_view_inactive_enabled(self):
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1@example.com",
                "slug": self.bink_scheme_inactive.slug,
                "locale": "en_GB",
                "bundle_id": self.BINK_BUNDLE_ID,
            },
        )

        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content, "Bad request parameter")

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    def test_view_active_disabled(self):
        self.bink_bundle.magic_link_url = ""
        self.bink_bundle.save()
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1@example.com",
                "slug": self.bink_scheme_active.slug,
                "locale": "en_GB",
                "bundle_id": self.BINK_BUNDLE_ID,
            },
        )

        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content, "Bad request parameter")

    def test_view_active_bad_email(self):
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1",
                "slug": self.bink_scheme_active.slug,
                "locale": "en_GB",
                "bundle_id": self.BINK_BUNDLE_ID,
            },
        )

        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content, "Bad email parameter")

    def test_view_active_bad_locale(self):
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1@example.com",
                "slug": self.bink_scheme_active.slug,
                "locale": "en_US",
                "bundle_id": self.BINK_BUNDLE_ID,
            },
        )

        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content, "Bad request parameter")

    def test_view_unknown_bundle(self):
        response = self.client.post(
            reverse("user_make_magic_link"),
            {
                "email": "test_1@example.com",
                "slug": self.bink_scheme_active.slug,
                "locale": "en_GB",
                "bundle_id": "unknown",
            },
        )

        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content, "Bad request parameter")

    @patch.object(ClientApplicationBundle, "template", new_callable=PropertyMock)
    def test_serializer_valid_data(self, mock_template):
        mock_template.return_value.read.return_value = b"{{ magic_link_url }}"
        email = "test_1@example.com"
        serializer = MakeMagicLinkSerializer(
            data={
                "email": email,
                "slug": self.bink_scheme_active.slug,
                "locale": "en_GB",
                "bundle_id": self.BINK_BUNDLE_ID,
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(email, serializer.validated_data["email"])
        self.assertEqual("en_GB", serializer.validated_data["locale"])
        self.assertEqual(self.BINK_BUNDLE_ID, serializer.validated_data["bundle_id"])
        self.assertEqual(self.bink_scheme_active.slug, serializer.validated_data["slug"])
        self.assertEqual(self.url, serializer.validated_data["url"])
        token = serializer.validated_data["token"]
        token_data = jwt.decode(token, key=self.bink_web_secret, algorithms=["HS512"])
        self.assertEqual(email, token_data["email"])
        self.assertEqual(self.BINK_BUNDLE_ID, token_data["bundle_id"])
        token_age = arrow.utcnow().int_timestamp - token_data["iat"]
        # Make sure execution time does cause a failed test error on timestamp < 30 secs
        self.assertLess(token_age, 30)
        token_life_mins = int((token_data["exp"] - token_data["iat"]) / 60)
        self.assertEqual(self.lifetime, token_life_mins)
