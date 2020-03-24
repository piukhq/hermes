import arrow
from django.test import TestCase

from scheme import vouchers
from scheme.models import Category, Scheme, SchemeAccount, VoucherScheme

TEST_SLUG = "fatface"


class TestVouchers(TestCase):
    def setUp(self):
        category = Category.objects.create()
        self.scheme = Scheme.objects.create(tier=Scheme.PARTNER, category=category, slug=TEST_SLUG)
        VoucherScheme.objects.create(
            scheme=self.scheme,
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
            terms_and_conditions_url="https://example.com",
            body_text_inprogress="voucher body",
            body_text_issued="voucher body",
            body_text_redeemed="voucher body",
            body_text_expired="voucher body",
        )
        VoucherScheme.objects.create(
            scheme=self.scheme,
            barcode_type=1,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_STAMPS,
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
            terms_and_conditions_url="https://example.com",
            body_text_inprogress="voucher body",
            body_text_issued="voucher body",
            body_text_redeemed="voucher body",
            body_text_expired="voucher body",
        )
        VoucherScheme.objects.create(
            scheme=self.scheme,
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
        )

    def test_accumulator_inprogress_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_accumulator_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_accumulator_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_accumulator_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_stamps_inprogress_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.VoucherState.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_stamps_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.VoucherState.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_stamps_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.VoucherState.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_stamps_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_STAMPS)
        headline_template = vs.get_headline(vouchers.VoucherState.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_join_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.VoucherState.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_join_redeemed_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.VoucherState.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_join_expired_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.VoucherState.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_make_voucher(self):
        now = arrow.utcnow().timestamp
        voucher_fields = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "type": vouchers.VoucherType.ACCUMULATOR.value,
            "value": 300,
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
