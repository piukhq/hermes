import os
import typing as t
from datetime import datetime
from unittest.mock import MagicMock, patch

import factory.django
from django.conf import settings
from django.test import override_settings
from rest_framework import serializers
from shared_config_storage.credentials.encryption import BLAKE2sHash, RSACipher

from history.utils import GlobalMockAPITestCase
from payment_card.tests.factories import IssuerFactory, PaymentCardFactory
from scheme.tests.factories import SchemeFactory, SchemeImageFactory
from ubiquity.channel_vault import SecretKeyName
from ubiquity.models import ServiceConsent
from ubiquity.tests.factories import ServiceConsentFactory
from ubiquity.versioning.base.serializers import MembershipPlanSerializer as base_MembershipPlanSerializer
from ubiquity.versioning.base.serializers import ServiceSerializer, UbiquityImageSerializer
from ubiquity.versioning.v1_2.serializers import MembershipPlanSerializer as MembershipPlanSerializerV1_2
from ubiquity.versioning.v1_2.serializers import (
    PaymentCardTranslationSerializer as PaymentCardTranslationSerializerV1_2,
)
from ubiquity.versioning.v1_3.serializers import MembershipPlanSerializer as MembershipPlanSerializerV1_3
from user.tests.factories import ClientApplicationBundleFactory, UserFactory

private_key = (
    "-----BEGIN RSA PRIVATE KEY-----\nMIIJJwIBAAKCAgEAr4Exi9NZlKwjFn8G6tapAGjEvn/E77Nbq0UZfiGFfsf3O"
    "9Qu\ndno8l8iuqUMIq2LZLFntijNgp7gu2jeRaeF3+ti0D7D+vp9XqNO4bWHi7DhBsSzO\nD6do3qn5q1iw9fNLcVwDFM4"
    "PVqFn6bl1CkmIcQLEVeLWBeK5/UWXoPM5XI+gwQNJ\nAc9wMlayw4o0ohCi25vqyOlcXL5yi/S9kpnyh0f8rPp3i7KG3F2"
    "izKNexiHouW7t\nuzTAhXUk85NHFLB/UyZwKeirBmaJnqk6SwVZrtsle0ixXwVVF4lLoJmtNRRzYOFp\nMtEbnKqtYFsVy"
    "a3T6ZokdPdw/8VjsrSVnjHeW133oKmzxvmNqFVTRr1+uQNYNoxz\nd5HlSR2ttotYS+/TrH4XVV50lJzaEjZZuTbvGUn31"
    "vlr1aAeemEC7dmUF+DjGgPA\noYBfgtnCg1h7qEGhVN3k4RvAX+7kPuwcefQ7pVxFg4RDJxf9bT2Ev6ldKLeDDe7A\nuTV"
    "HJyAQaW1XHbE32Mz4Rhaz/CCReuLZzJJT9CD6YiZcRkVso0DL5wGkoz3kAUE5\nTXzbQ7z7ot4yruBO1JcirUQHdKjTXWz"
    "b1v0SvmJIr+urYXTV3D3ejE62ym8u8P9K\njrit4ULSerafjCg+pxXk1H5M76hdbqh9nUBjLtIpjxeiT/XDBoMUiicmbr8"
    "CAwEA\nAQKCAgAgHdtMRDP7cfjF0B8a8IdizMlcNxN57e+TiwScQVQlnEBREYYjJkFaYV4d\nGWhHvMITTK2cgcRpTNo+E"
    "rcokhsbq3Zf/LrRdWVcPspcMfKN2cmju5hF4xPc02we\nAA/6IjinGPhzYTYLW2QhsE+Lv2MZkzEMqoMR9qikgYy65meT2"
    "bDIQWqlyykz/Quf\nnvX8xmCXIZQ4igPd8PgTRok+f6+TNAg4O2mPBe+J+hSlsCvSxDfLX1Jf1Mp6YbKO\nZGA4mAfk1n7"
    "mHG7XsAH1J/DD88mypuXYBrh2tAobUYOmcxjwQrrOetF+fCe6Zr1t\niZ2WF5pVAGE1imaCV8Pj2woaNfQDpKmY51Bgn+v"
    "3bOs0QV4JBl8Tw5Bn6ocn/I8w\nn0kAxB/FmSwJbqOXgY5yZIlIJQdrEabahh/8n72HETH/I+iDXgAYFTH2yQe8ZfCD\nL"
    "ySqd2uaauDYhTue3FaIvkdYmSa2brMpVkmoTZSGoHwrMxaddYXPfFL779IjP7/9\nDGNuWuQen0LgJMCRH1zJWF+aJojrd"
    "uMwy0WImh/KxmcjfOiTgg5DgV1gbkcVfjYP\n1YrW2BRHSKvwB+U9i4UE+HmK0ztIA50+U9SHOXpOsWkSJfrjCKVPR4uLV"
    "PseboW8\n1UYuSWX39LSYhTNNFBs3XxwW+Mn069ReiXi05Vo73qA/asDp6QKCAQEA3aMTVaOo\nl8Vli3rdSU8cK3UtkUO"
    "3bA3oRzVLizUIIiMnY0ifK5OWMpk1nv/MGw3DWXKoLUYW\nRJxkq5n/QpgmCEmIQHyuOT+auZCdQW/4+NmwdubtB8l+8AD"
    "L5vh14633zw5UH+JV\neb7zXGBeUQQ4W8GeIm85nkcNWOuiBvR8vL3aPG/K5mSMARxfNR4IYFjI3z0vlMNX\nZcEUqhIpw"
    "kVVbyc1bibp0v7Q5vfqh4O9EhqKxj0eULPehWmphxTKakgGHFswR6Bs\nuOno55r/8Orv9mG3tN6jPxq43gpJkzhZvuhIk"
    "EunnndwKcr953YBnACdETm/gkRC\nm1TSC1votYgJgwKCAQEAyrcX7a69kot173bsCQCqN+tbZ6mEnadW2qEI/e0AtgFt\n"
    "J+vr04bY8zV8R4Zlcyavog4G4ZxDv/VKx7kkbQaXIwtMRqtJIXWkw/C6O1YwmGB1\ny0/DaG03ydtr6npXQonjJF+tYv2n"
    "sKBdCoO9FXQkoZ1XP2Ip9Ghv+X5JPQHEXFs5\nYqv4eZ4vbOFsQW0TG5EJqaLoBPbg675SdBrCF4+fNPeicWVi1qIzaU9Y"
    "44Isl/DO\neyrU8mchO4r93xtQ3Qe9/v184reUBCT7mpNOOkwpocyxFhtXlIDrcBH/glPYfZxE\n5H1rw20yUho7bN/yHd"
    "Kem78HJmKtJYLyxLENTdYNFQKCAQBaE2vJM2FShWQ2orGK\nmL8/Hjltv1KtdJ2BSzSvl9b9YMIiRKKD6FBzsfar7xP5rs"
    "dE9CdLdx+XtOPpJgYq\n/4D9fz0D0GhSVfpBDngK30IViQuB12pf7tFLI1e7QCFRbiO3oAAqkSbh+uwXEAdk\n780j5XWq"
    "Uv/cxs2y5NkN8JE9d/9Y7qpMpnKMBQbgpJsM5SiGKezLjfRYI3eNgyI7\nlUgai5nYcbI4EV2/cOR9PNo7oFPkK3TFocR+"
    "/ilq/9UgCrOJFLpzccyd/lqsvj7k\nn+b0gFRUCuPXwrl9bDrovU8kGm1bT5QJAEuygJBeYIRY7ZroJEsj2zAixv8ypKDY"
    "\nHjiXAoIBAGeJZqZWRqsPoffh9KKQfWA8TJ5AneRr8NePwmj3YRKU3eyy+es7B5oI\n6mYZxb0vuCr8IRWgW5YysbQa4v"
    "jwkccrYRUDLUHytWoCjQv7dKyPL/rczYCLsB/g\ne1jyjZkFlkcguw1BYyG6dmsFaFEJ1h/ZnhNYjvcvVGnIz51iRqmpSk"
    "EUdr+fRLfG\n1yT/ke/Vf2ruMrU+ZxjhR3nXpOSlzXofNQ/X6ciYZcvW5B6ngSFFtCCCeusoM3gX\nAJ2wdPe/mZIgZGXj"
    "v6zyOrPzotPxzJ3AT35sDqphwl6mQquNKZjWdPWC/cR+BGKc\n1VdBdoc26R3BTuSTJ75uCJLfn1zvBBUCggEAFB/rtevJ"
    "gxy8PFR3gsxDZ/riULOP\nb82x9GKu97loKIyC35ry5IQLGi42F28jGOHqDcRi+2wwYdJwIbfmku4+VOhpLVkZ\nko90qz"
    "8YoTx8JSacU2nOn9q+hARH+NZNzWsfug7//WYOIialRjKevHL1XZEG6pqi\n5KEwABBDkTWUFc4UMeHm2A8ptpvVR5bHsh"
    "2jntdtx+pI9NlayftxUQuuSff+LAST\nxA6j6PnkpnyK886MgDwXnT5WzLos6k+uoDVtqTgGz57eltaTeOLacHyNhAiHwC"
    "lQ\nfstd3HfzpQW4Vde0qPGmWY5LlkMt8gBu7yJsCL0M0abDl2JQgyHCkNBO6Q==\n-----END RSA PRIVATE KEY-----"
)

mock_secrets = {
    "bundle_secrets": {
        "com.barclays.test": {
            "private_key": private_key,
            "public_key": (
                "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCvgTGL01mUrCMWfwbq1qkAaMS+f8Tvs1urRRl+IYV+x/c"
                "71C52ejyXyK6pQwirYtksWe2KM2CnuC7aN5Fp4Xf62LQPsP6+n1eo07htYeLsOEGxLM4Pp2jeqfmrWLD180"
                "txXAMUzg9WoWfpuXUKSYhxAsRV4tYF4rn9RZeg8zlcj6DBA0kBz3AyVrLDijSiEKLbm+rI6VxcvnKL9L2Sm"
                "fKHR/ys+neLsobcXaLMo17GIei5bu27NMCFdSTzk0cUsH9TJnAp6KsGZomeqTpLBVmu2yV7SLFfBVUXiUug"
                "ma01FHNg4Wky0Rucqq1gWxXJrdPpmiR093D/xWOytJWeMd5bXfegqbPG+Y2oVVNGvX65A1g2jHN3keVJHa2"
                "2i1hL79OsfhdVXnSUnNoSNlm5Nu8ZSffW+WvVoB56YQLt2ZQX4OMaA8ChgF+C2cKDWHuoQaFU3eThG8Bf7u"
                "Q+7Bx59DulXEWDhEMnF/1tPYS/qV0ot4MN7sC5NUcnIBBpbVcdsTfYzPhGFrP8IJF64tnMklP0IPpiJlxGR"
                "WyjQMvnAaSjPeQBQTlNfNtDvPui3jKu4E7UlyKtRAd0qNNdbNvW/RK+Ykiv66thdNXcPd6MTrbKby7w/0qO"
                "uK3hQtJ6tp+MKD6nFeTUfkzvqF1uqH2dQGMu0imPF6JP9cMGgxSKJyZuvw== test@bink.com"
            ),
        }
    },
    "secret_keys": {SecretKeyName.PCARD_HASH_SECRET: "secret"},
}


class TestBaseSerializers(GlobalMockAPITestCase):
    def test_service_serializer(self):
        serializer_class = ServiceSerializer
        valid_data = {
            "consent": {"email": "testuser@bink.com", "timestamp": 1610114377},
        }

        valid_data_float_timestamp = {
            "consent": {"email": "testuser@bink.com", "timestamp": 1610114377.11},
        }

        valid_data_str_timestamp = {
            "consent": {"email": "testuser@bink.com", "timestamp": "1610114377"},
        }

        valid_data_float_str_timestamp = {
            "consent": {"email": "testuser@bink.com", "timestamp": "1610114377.11"},
        }

        valid_data_with_optionals = {
            "consent": {
                "email": "testuser@bink.com",
                "timestamp": 1610114377,
                "longitude": 1.1,
                "latitude": 2.2,
            },
        }

        valid_data_with_optionals_zero_values_1 = {
            "consent": {
                "email": "testuser@bink.com",
                "timestamp": 1610114377,
                "longitude": 0.0,
                "latitude": 2.2,
            },
        }

        valid_data_with_optionals_zero_values_2 = {
            "consent": {
                "email": "testuser@bink.com",
                "timestamp": 1610114377,
                "longitude": 1.1,
                "latitude": 0,
            },
        }

        valid_data_with_optionals_zero_values_3 = {
            "consent": {
                "email": "testuser@bink.com",
                "timestamp": 1610114377,
                "longitude": 0.0,
                "latitude": 0,
            },
        }

        missing_consent_email_data = {
            "consent": {"bademail": "testuser@bink.com", "timestamp": 1610114377},
        }

        missing_consent_timestamp_data = {
            "consent": {"email": "testuser@bink.com", "badtimestamp": 1610114377},
        }

        missing_consent_data = {
            "badconsent": {"email": "testuser@bink.com", "timestamp": 1610114377},
        }

        invalid_consent_email_data = {
            "consent": {"email": "notanemail", "timestamp": 1610114377},
        }

        invalid_consent_timestamp_data = {
            "consent": {"email": "testuser@bink.com", "timestamp": "12/12/2020"},
        }

        all_valid_data_with_optionals_list = (
            valid_data_with_optionals,
            valid_data_with_optionals_zero_values_1,
            valid_data_with_optionals_zero_values_2,
            valid_data_with_optionals_zero_values_3,
        )

        all_invalid_data_list = (
            missing_consent_email_data,
            missing_consent_timestamp_data,
            missing_consent_data,
            invalid_consent_email_data,
            invalid_consent_timestamp_data,
        )

        for data in (valid_data, valid_data_float_timestamp, valid_data_str_timestamp, valid_data_float_str_timestamp):
            serializer = serializer_class(data=data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            self.assertIn("email", validated_data["consent"])
            self.assertIn("timestamp", validated_data["consent"])

        for data in all_valid_data_with_optionals_list:
            serializer = serializer_class(data=data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            self.assertIn("email", validated_data["consent"])
            self.assertIn("timestamp", validated_data["consent"])
            self.assertIn("latitude", validated_data["consent"])
            self.assertIn("longitude", validated_data["consent"])

        for invalid_data in all_invalid_data_list:
            with self.assertRaises(serializers.ValidationError):
                serializer = serializer_class(data=invalid_data)
                serializer.is_valid(raise_exception=True)

    def test_service_deserializer(self):
        serializer_class = ServiceSerializer

        service_consent_1 = ServiceConsentFactory(latitude=1, longitude=2)
        service_consent_2 = ServiceConsentFactory(latitude=1.1, longitude=2.2)
        service_consent_3 = ServiceConsentFactory(latitude=0, longitude=1.1)
        service_consent_4 = ServiceConsentFactory(latitude=1.1, longitude=0)
        service_consent_5 = ServiceConsentFactory(latitude=0.0, longitude=0)
        service_consent_6 = ServiceConsentFactory(latitude=0, longitude=0.0)

        all_consents = (
            service_consent_1,
            service_consent_2,
            service_consent_3,
            service_consent_4,
            service_consent_5,
            service_consent_6,
        )

        for instance in all_consents:
            consent = serializer_class(instance).data

            self.assertIn("consent", consent)
            self.assertIn("email", consent["consent"])
            self.assertIn("timestamp", consent["consent"])
            self.assertIn("latitude", consent["consent"])
            self.assertEqual(consent["consent"]["latitude"], instance.latitude)
            self.assertTrue(isinstance(consent["consent"]["latitude"], float))
            self.assertIn("longitude", consent["consent"])
            self.assertEqual(consent["consent"]["longitude"], instance.longitude)
            self.assertTrue(isinstance(consent["consent"]["longitude"], float))

        # This does not use ServiceConsentFactory because that would save the instance and attempts to convert
        # latitude and longitude to float values. The test checks that deserializing pre-saved instances
        # will attempt to convert lat/long to floats and fail gracefully.
        service_consent_7 = ServiceConsent(
            user=UserFactory(), timestamp=datetime(2019, 1, 1, 12, 00), latitude="hello", longitude=0.0
        )
        service_consent_8 = ServiceConsentFactory(latitude=0.0)
        service_consent_9 = ServiceConsentFactory(longitude=0.0)

        for instance in (service_consent_7, service_consent_8, service_consent_9):
            consent = serializer_class(instance).data

            self.assertIn("consent", consent)
            self.assertNotIn("latitude", consent["consent"])
            self.assertNotIn("longitude", consent["consent"])

    def test_service_create(self):
        client_application_bundle = ClientApplicationBundleFactory.create()

        request = MagicMock()
        request.channels_permit.auth_by = "external"
        request.channels_permit.client.pk = client_application_bundle.client.pk
        request.channels_permit.bundle_id = client_application_bundle.bundle_id
        request.prop_id = "some_external_id"

        serializer_class = ServiceSerializer
        valid_data_with_optionals = {
            "consent": {
                "email": "testuser@bink.com",
                "timestamp": 1610114377,
                "longitude": 1.1,
                "latitude": 2.2,
            },
        }
        serializer = serializer_class(data=valid_data_with_optionals, context={"request": request})
        serializer.is_valid(raise_exception=True)
        service_consent, service_consent_created = serializer.save()

        self.assertTrue(service_consent_created)
        self.assertEqual(request.prop_id, service_consent.user.external_id)

    @override_settings(NO_AZURE_STORAGE=True)
    def test_ubiquity_image_deserializer(self):
        serializer_class = UbiquityImageSerializer

        image1 = SchemeImageFactory(image=factory.django.ImageField())

        image = serializer_class(image1).data

        self.assertEqual(image1.id, image["id"])

        url = os.path.join(settings.CONTENT_URL, image1.image.name)
        self.assertEqual(url, image["url"])
        self.assertEqual(image1.image_type_code, image["type"])
        self.assertEqual(image1.description, image["description"])

    @override_settings(
        NO_AZURE_STORAGE=False, CONTENT_URL="https://api.dev.gb.bink.com/content/hermes", AZURE_CONTAINER="media/hermes"
    )
    def test_ubiquity_image_deserializer_azure(self):
        serializer_class = UbiquityImageSerializer

        image1 = SchemeImageFactory(image=factory.django.ImageField())

        image = serializer_class(image1).data

        self.assertEqual(image1.id, image["id"])

        url = os.path.join("https://api.dev.gb.bink.com/content/hermes", image1.image.name)
        self.assertEqual(url, image["url"])
        self.assertEqual(image1.image_type_code, image["type"])
        self.assertEqual(image1.description, image["description"])

    def test_membership_plan(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = base_MembershipPlanSerializer(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertFalse("slug" in serialized_data.keys())
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"])

    def test_membership_plan_no_go_live_returned(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
            "go_live": datetime.today(),
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = base_MembershipPlanSerializer(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertFalse("slug" in serialized_data.keys())
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"])
        # go live check
        self.assertNotIn("go_live", serialized_data.keys())


class TestSerializersV1_2(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.bundle_id = "com.barclays.test"
        cls.rsa = RSACipher()
        cls.pub_key = mock_secrets["bundle_secrets"][cls.bundle_id]["public_key"]

        IssuerFactory(name="Barclays")
        PaymentCardFactory(slug="mastercard")

    @patch("ubiquity.channel_vault._secret_keys", mock_secrets["secret_keys"])
    @patch("ubiquity.channel_vault._bundle_secrets", mock_secrets["bundle_secrets"])
    def test_payment_card_translation_serializer(self):
        serializer = PaymentCardTranslationSerializerV1_2
        data = {
            "fingerprint": "testfingerprint00068",
            "token": "testtoken00068",
            "name_on_card": "Test Card",
            "first_six_digits": self.rsa.encrypt("555555", pub_key=self.pub_key),
            "last_four_digits": self.rsa.encrypt("4444", pub_key=self.pub_key),
            "month": self.rsa.encrypt(12, pub_key=self.pub_key),
            "year": self.rsa.encrypt(2025, pub_key=self.pub_key),
        }

        expected_data = {
            "fingerprint": "testfingerprint00068",
            "token": "testtoken00068",
            "name_on_card": "Test Card",
            "pan_start": "555555",
            "pan_end": "4444",
            "expiry_month": 12,
            "expiry_year": 2025,
        }

        serialized_data = serializer(data.copy(), context={"bundle_id": self.bundle_id}).data
        self.assertTrue(expected_data.items() < serialized_data.items())

        data_unencrypted = {
            "fingerprint": "testfingerprint00068",
            "token": "testtoken00068",
            "name_on_card": "Test Card",
            "first_six_digits": "555555",
            "last_four_digits": "4444",
            "month": 12,
            "year": 2025,
        }

        serialized_data = serializer(data_unencrypted, context={"bundle_id": self.bundle_id}).data
        self.assertTrue(expected_data.items() < serialized_data.items())

        hash1 = "hash1"
        hash2 = BLAKE2sHash().new(
            obj=hash1, key=t.cast(str, mock_secrets["secret_keys"][SecretKeyName.PCARD_HASH_SECRET])
        )
        data["hash"] = self.rsa.encrypt(hash1, pub_key=self.pub_key)
        expected_data["hash"] = hash2

        serialized_data = serializer(data.copy(), context={"bundle_id": self.bundle_id}).data
        self.assertTrue(expected_data.items() < serialized_data.items())

    @patch("ubiquity.channel_vault._secret_keys", mock_secrets["secret_keys"])
    @patch("ubiquity.channel_vault._bundle_secrets", mock_secrets["bundle_secrets"])
    def test_payment_card_translation_serializer_raises_error_for_incorrect_encryption(self):
        serializer = PaymentCardTranslationSerializerV1_2
        hash1 = "hash1"
        data = {
            "fingerprint": "testfingerprint00068",
            "token": "testtoken00068",
            "name_on_card": "Test Card",
            "hash": self.rsa.encrypt("aGFzaDE", pub_key=self.pub_key) + "wrong",
            "first_six_digits": self.rsa.encrypt("555555", pub_key=self.pub_key),
            "last_four_digits": self.rsa.encrypt("4444", pub_key=self.pub_key),
            "month": self.rsa.encrypt(12, pub_key=self.pub_key),
            "year": self.rsa.encrypt(2025, pub_key=self.pub_key),
        }

        # Test base64 encoded but the value is not encrypted
        with self.assertRaises(ValueError) as e:
            serializer(data, context={"bundle_id": self.bundle_id}).data

        self.assertEqual(e.exception.args[0], "Failed to decrypt sensitive fields")

        data = {
            "fingerprint": "testfingerprint00068",
            "token": "testtoken00068",
            "name_on_card": "Test Card",
            "hash": self.rsa.encrypt(hash1, pub_key=self.pub_key),
            "first_six_digits": self.rsa.encrypt("555555", pub_key=self.pub_key) + "wrong",
            "last_four_digits": self.rsa.encrypt("4444", pub_key=self.pub_key),
            "month": self.rsa.encrypt(12, pub_key=self.pub_key),
            "year": self.rsa.encrypt(2025, pub_key=self.pub_key),
        }

        # Test value is not encrypted or base64 encoded
        with self.assertRaises(ValueError) as e:
            serializer(data, context={"bundle_id": self.bundle_id}).data

        self.assertEqual(e.exception.args[0], "Failed to decrypt sensitive fields")

    def test_membership_plan(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = MembershipPlanSerializerV1_2(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertFalse("slug" in serialized_data.keys())
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"])

    def test_membership_plan_no_go_live_returned(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
            "go_live": datetime.today(),
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = MembershipPlanSerializerV1_2(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertFalse("slug" in serialized_data.keys())
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"]),
        # go live check
        self.assertNotIn("go_live", serialized_data.keys())


class TestSerializersV1_3(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.image1 = SchemeImageFactory(
            image=factory.django.ImageField(),
            dark_mode_image=factory.django.ImageField(),
        )

    @override_settings(NO_AZURE_STORAGE=True)
    def test_dark_mode_url(self):
        serializer_class = MembershipPlanSerializerV1_3.image_serializer_class

        image = serializer_class(self.image1).data

        self.assertEqual(self.image1.id, image["id"])

        url = os.path.join(settings.CONTENT_URL, self.image1.image.name)
        self.assertEqual(url, image["url"])

        dark_mode_url = os.path.join(settings.CONTENT_URL, self.image1.dark_mode_image.name)
        self.assertEqual(dark_mode_url, image["dark_mode_url"])

        self.assertEqual(self.image1.image_type_code, image["type"])
        self.assertEqual(self.image1.description, image["description"])

    @override_settings(
        NO_AZURE_STORAGE=False, CONTENT_URL="https://api.dev.gb.bink.com/content/hermes", AZURE_CONTAINER="media/hermes"
    )
    def test_dark_mode_url_azure(self):
        serializer_class = MembershipPlanSerializerV1_3.image_serializer_class

        image = serializer_class(self.image1).data

        self.assertEqual(self.image1.id, image["id"])

        url = os.path.join("https://api.dev.gb.bink.com/content/hermes", self.image1.image.name)
        self.assertEqual(url, image["url"])

        dark_mode_url = os.path.join("https://api.dev.gb.bink.com/content/hermes", self.image1.dark_mode_image.name)
        self.assertEqual(dark_mode_url, image["dark_mode_url"])

        self.assertEqual(self.image1.image_type_code, image["type"])
        self.assertEqual(self.image1.description, image["description"])

    def test_membership_plan(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
            "go_live": datetime.today(),
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = MembershipPlanSerializerV1_3(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertEqual(expected_data["slug"], serialized_data["slug"])
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"])
        # go live check
        self.assertEqual(expected_data["go_live"].isoformat(), serialized_data["go_live"])

    def test_membership_plan_with_no_go_live(self):
        expected_data = {
            "slug": "fake_slug_is_still_slug",
            "name": "Insert fake plan_name",
            "url": "https://fake.co.uk/plan_url",
            "company": "Insert fake company_name",
            "company_url": "https://fake.co.uk/company_url",
            "forgotten_password_url": "https://fake.co.uk/forgiven_but_not_forgotten",
            "scan_message": "scan_message goes here",
        }
        mock_request_context = MagicMock()
        scheme = SchemeFactory(**expected_data)
        serialized_data = MembershipPlanSerializerV1_3(scheme, context={"request": mock_request_context}).data
        # slug check
        self.assertEqual(expected_data["slug"], serialized_data["slug"])
        # account checks
        self.assertEqual(expected_data["company"], serialized_data["account"]["company_name"])
        self.assertEqual(expected_data["name"], serialized_data["account"]["plan_name"])
        self.assertEqual(expected_data["company_url"], serialized_data["account"]["company_url"])
        self.assertEqual(expected_data["url"], serialized_data["account"]["plan_url"])
        self.assertEqual(expected_data["forgotten_password_url"], serialized_data["account"]["forgotten_password_url"])
        # card checks
        self.assertEqual(expected_data["scan_message"], serialized_data["card"]["scan_message"])
        # go live check
        self.assertNotIn("go_live", serialized_data.keys())
