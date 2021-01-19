import arrow
from django.test import TestCase

from history.utils import GlobalMockAPITestCase
from scheme import vouchers
from scheme.models import Category, Scheme, SchemeAccount, VoucherScheme

TEST_SLUG = "fatface"


class TestVouchers(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create()
        cls.scheme = Scheme.objects.create(tier=Scheme.PARTNER, category=category, slug=TEST_SLUG)
        VoucherScheme.objects.create(
            scheme=cls.scheme,
            barcode_type=1,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR,
            earn_prefix="£",
            earn_suffix="pounds",
            earn_currency="GBP",
            burn_type=VoucherScheme.BURNTYPE_VOUCHER,
            burn_value=5,
            burn_prefix="£",
            headline_inprogress="{{earn_prefix}}{{earn_target_remaining|floatformat:2}} left to go!",
            headline_issued="{{burn_prefix}}{{burn_value|floatformat:2}} voucher earned",
            headline_redeemed="Voucher redeemed",
            headline_expired="Voucher expired",
            headline_cancelled="Voucher cancelled",
            terms_and_conditions_url="https://example.com",
            body_text_inprogress="voucher body",
            body_text_issued="voucher body",
            body_text_redeemed="voucher body",
            body_text_expired="voucher body",
            body_text_cancelled="voucher body",
        )
        VoucherScheme.objects.create(
            scheme=cls.scheme,
            barcode_type=1,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_STAMPS,
            earn_prefix="£",
            earn_suffix="pounds",
            earn_currency="GBP",
            earn_target_value=7,
            burn_type=VoucherScheme.BURNTYPE_VOUCHER,
            burn_value=5,
            burn_prefix="£",
            headline_inprogress="{{earn_prefix}}{{earn_target_remaining|floatformat:2}} left to go!",
            headline_issued="{{burn_prefix}}{{burn_value|floatformat:2}} voucher earned",
            headline_redeemed="Voucher redeemed",
            headline_expired="Voucher expired",
            headline_cancelled="Voucher cancelled",
            terms_and_conditions_url="https://example.com",
            body_text_inprogress="voucher body",
            body_text_issued="voucher body",
            body_text_redeemed="voucher body",
            body_text_expired="voucher body",
            body_text_cancelled="voucher body",
        )
        VoucherScheme.objects.create(
            scheme=cls.scheme,
            barcode_type=2,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_JOIN,
            earn_prefix="£",
            earn_suffix="pounds",
            earn_currency="GBP",
            burn_type=VoucherScheme.BURNTYPE_VOUCHER,
            burn_value=5,
            burn_prefix="£",
            headline_issued="{{burn_prefix}}{{burn_value|floatformat:2}} voucher earned",
            headline_redeemed="Voucher redeemed",
            headline_expired="Voucher expired",
            headline_cancelled="Voucher cancelled",
        )

    def test_accumulator_inprogress_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_accumulator_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_accumulator_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_accumulator_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_accumulator_cancelled_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_stamps_inprogress_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_stamps_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_stamps_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_stamps_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_stamps_cancelled_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_join_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_join_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_join_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_join_cancelled_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_make_voucher(self):
        now = arrow.utcnow().timestamp
        voucher_fields = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "type": vouchers.VoucherType.ACCUMULATOR.value,
            "value": 300,
            "target_value": 400,
            "state": "redeemed"
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG)
        vs: VoucherScheme = VoucherScheme.objects.get(scheme=scheme, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        account = SchemeAccount.objects.create(scheme=scheme, order=0)
        voucher = account.make_single_voucher(voucher_fields)
        self.assertEqual(
            voucher,
            {
                "earn": {
                    "type": "accumulator",
                    "prefix": vs.earn_prefix,
                    "suffix": vs.earn_suffix,
                    "currency": vs.earn_currency,
                    "value": 300,
                    "target_value": 400,
                },
                "burn": {
                    "type": vs.burn_type,
                    "currency": vs.burn_currency,
                    "prefix": vs.burn_prefix,
                    "suffix": vs.burn_suffix,
                    "value": vs.burn_value,
                },
                "code": "abc123",
                "date_issued": now,
                "date_redeemed": now,
                "expiry_date": now + 1000,
                "headline": vs.headline_redeemed,
                "body_text": "voucher body",
                "subtext": "",
                "state": "redeemed",
                "barcode_type": vs.barcode_type,
                "terms_and_conditions_url": "https://example.com",
            },
        )

    def test_make_voucher_sans_expiry_and_redeem_dates(self):
        now = arrow.utcnow().timestamp
        voucher_fields = {
            "issue_date": now,
            "code": "abc123",
            "type": vouchers.VoucherType.ACCUMULATOR.value,
            "value": 300,
            "target_value": 0,
            "state": "issued"
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG)
        vs: VoucherScheme = VoucherScheme.objects.get(scheme=scheme, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        account = SchemeAccount.objects.create(scheme=scheme, order=0)
        voucher = account.make_single_voucher(voucher_fields)
        self.assertEqual(
            voucher,
            {
                "earn": {
                    "type": "accumulator",
                    "prefix": vs.earn_prefix,
                    "suffix": vs.earn_suffix,
                    "currency": vs.earn_currency,
                    "value": 300,
                    "target_value": 0,
                },
                "burn": {
                    "type": vs.burn_type,
                    "currency": vs.burn_currency,
                    "prefix": vs.burn_prefix,
                    "suffix": vs.burn_suffix,
                    "value": vs.burn_value,
                },
                "code": "abc123",
                "date_issued": now,
                "expiry_date": arrow.get(now).shift(months=vs.expiry_months).timestamp,
                "headline": "£5.00 voucher earned",
                "body_text": "voucher body",
                "subtext": "",
                "state": "issued",
                "barcode_type": vs.barcode_type,
                "terms_and_conditions_url": "https://example.com",
            },
        )

    def test_get_earn_target_value_from_voucher(self):
        """
        Test fetching the target value from the incoming voucher
        """
        # GIVEN
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        voucher_fields = {
            "target_value": 10
        }

        # WHEN
        earn_target_value = vs.get_earn_target_value(voucher_fields=voucher_fields)

        # THEN
        self.assertIsInstance(earn_target_value, float)
        self.assertEqual(10, earn_target_value)

    def test_get_earn_target_value_from_voucher_scheme(self):
        """
        Test fetching the target value from the voucher scheme: voucher's target_value and value are
        both None
        """
        # GIVEN
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        voucher_fields = {}

        # WHEN
        earn_target_value = vs.get_earn_target_value(voucher_fields=voucher_fields)

        # THEN
        self.assertIsInstance(earn_target_value, float)
        self.assertEqual(7, earn_target_value)

    def test_get_earn_target_value_raises_value_error(self):
        """
        Test that fetching the target value, when neither the incoming voucher or the voucher scheme
        have been set, raises a ValueError
        """
        # GIVEN
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        vs.earn_target_value = None
        voucher_fields = {}

        # THEN
        self.assertRaises(ValueError, vs.get_earn_target_value, voucher_fields)

    def test_get_earn_value_from_voucher_first(self):
        """
        Test getting the earn value from the incoming voucher, ahead of the earn_target_voucher
        """
        # GIVEN
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        expected_value = 8
        voucher_fields = {
            "value": expected_value
        }

        # WHEN
        earn_value = vs.get_earn_value(voucher_fields=voucher_fields, earn_target_value=12)

        # THEN
        self.assertEqual(expected_value, earn_value)

    def test_get_earn_value_assume_voucher_is_full(self):
        """
        Test that the earn value gets set to the earn target value, if the earn value is None.
        """
        # GIVEN
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        earn_target_value = 10
        voucher_fields = {
            "type": vouchers.VoucherType.STAMPS.value,
            "value": None,
        }

        # WHEN
        earn_value = vs.get_earn_value(voucher_fields=voucher_fields, earn_target_value=earn_target_value)

        # THEN
        self.assertEqual(earn_target_value, earn_value)
