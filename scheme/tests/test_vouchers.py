from django.test import TestCase

from scheme.models import Category, Scheme, VoucherScheme
from scheme import vouchers


TEST_SLUG = "fatface"


class TestVouchers(TestCase):
    def setUp(self):
        category = Category.objects.create()
        scheme = Scheme.objects.create(tier=Scheme.PARTNER, category=category, slug=TEST_SLUG)
        VoucherScheme.objects.create(
            scheme=scheme,
            barcode_type=0,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR,
            earn_prefix="£",
            burn_value=5,
            burn_prefix="£",
            headline_inprogress="{{earn_prefix}}{{earn_target_remaining|floatformat}} left to go!",
            headline_issued="{{burn_prefix}}{{burn_value|floatformat}} voucher earned",
            headline_redeemed="Voucher redeemed",
            headline_expired="Voucher expired",
        )
        VoucherScheme.objects.create(
            scheme=scheme,
            barcode_type=0,
            expiry_months=3,
            earn_type=VoucherScheme.EARNTYPE_JOIN,
            burn_value=5,
            burn_prefix="£",
            headline_issued="{{burn_prefix}}{{burn_value|floatformat}} voucher earned",
            headline_redeemed="Voucher redeemed",
            headline_expired="Voucher expired",
        )

    def test_accumulator_inprogress_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50 left to go!")

    def test_accumulator_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_ACCUMULATOR)
        headline_template = vs.get_headline(vouchers.VoucherState.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5 voucher earned")

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

    def test_join_issued_headline(self):
        vs = VoucherScheme.objects.get(scheme__slug=TEST_SLUG, earn_type=VoucherScheme.EARNTYPE_JOIN)
        headline_template = vs.get_headline(vouchers.VoucherState.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5 voucher earned")

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
