import datetime
from unittest.mock import patch

from django.core import mail
from rest_framework.test import APITestCase

from common.models import Image
from magic_link.tasks import send_magic_link, populate_template
from scheme.tests.factories import SchemeFactory, SchemeBundleAssociationFactory, SchemeImageFactory
from user.tests.factories import ClientApplicationBundleFactory
from user.utils import MagicLinkData


TEST_TEMPLATE = """
<h1>TEST EMAIL</h1>
<br>
<h2>
    Magic-link-url is {{ magic_link_url }}
    <br>
    Plan_name is: {{ plan_name }}
    <br>
    Plan_summary is: {{ plan_summary }}
    <br>
    Plan description is: {{ plan_description }}
    <br>
    Hero image is: {{ hero_image }}
    <br>
    Alt-hero image is: {{ alt_hero_image }}
    <br>

</h2>
"""


class TestTask(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_email = 'test-bink@bink.com'

    @patch('magic_link.tasks.populate_template', return_value='')
    def test_send_magic_link(self, mock_populate_template):
        magic_link_data = MagicLinkData(
            bundle_id="com.wasabi.bink.com",
            slug="wasabi-club",
            external_name="web",
            email=self.test_email,
            email_from="test_from_email@bink.com",
            subject="Some subject",
            template="Some template",
            url="magic/link/url",
            token="Some token",
            expiry_date=datetime.datetime.now(),
            locale="en_GB"
        )
        send_magic_link(magic_link_data)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Some subject')
        self.assertEqual(mail.outbox[0].from_email, 'test_from_email@bink.com')
        self.assertEqual(mail.outbox[0].reply_to, ['no-reply@bink.com'])

    def test_populate_template(self):
        bundle = ClientApplicationBundleFactory()
        scheme = SchemeFactory(plan_name="Some plan", plan_summary="Some summary", plan_description="Some description")
        image1 = SchemeImageFactory(scheme=scheme, image_type_code=Image.HERO)
        image2 = SchemeImageFactory(scheme=scheme, image_type_code=Image.ALT_HERO)

        SchemeBundleAssociationFactory(scheme=scheme, bundle=bundle)

        magic_link_data = MagicLinkData(
            bundle_id=bundle.bundle_id,
            slug=scheme.slug,
            external_name="web",
            email=self.test_email,
            email_from="test_from_email@bink.com",
            subject="Some subject",
            template=TEST_TEMPLATE,
            url="magic/link/url/?magic-link=",
            token="Some token",
            expiry_date=datetime.datetime.now(),
            locale="en_GB"
        )

        content = populate_template(magic_link_data)

        # Very basic check that tags have been substituted
        tag_to_value = {
            "{{ magic_link_url }}": magic_link_data.url + magic_link_data.token,
            "{{ plan_name }}": scheme.plan_name,
            "{{ plan_summary }}": scheme.plan_summary,
            "{{ plan_description }}": scheme.plan_description,
            "{{ hero_image }}": image1.image,
            "{{ alt_hero_image }}": image2.image,
        }

        for tag, value in tag_to_value.items():
            self.assertNotIn(tag, content)
            self.assertIn(str(value), content)
