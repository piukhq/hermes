from unittest import mock

import arrow

from history.utils import GlobalMockAPITestCase
from scheme import vouchers
from scheme.models import Category, Scheme, SchemeAccount, VoucherScheme, logger
from scheme.vouchers import VoucherStateStr

TEST_SLUG_STAMPS = "stamps_scheme"
TEST_SLUG_ACCUMULATOR = "accumulator_scheme"
TEST_SLUG_ACCUMULATOR_PERCENT = "accumulator_scheme_percent"
TEST_SLUG_JOIN = "join_scheme"


class TestVouchers(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create()
        cls.maxDiff = None
        cls.scheme_stamps = Scheme.objects.create(tier=Scheme.ENGAGE, category=category, slug=TEST_SLUG_STAMPS)
        cls.scheme_accumulator = Scheme.objects.create(
            tier=Scheme.ENGAGE, category=category, slug=TEST_SLUG_ACCUMULATOR
        )
        cls.scheme_accumulator_percent_headline = Scheme.objects.create(
            tier=Scheme.ENGAGE, category=category, slug=TEST_SLUG_ACCUMULATOR_PERCENT
        )
        cls.scheme_join = Scheme.objects.create(tier=Scheme.ENGAGE, category=category, slug=TEST_SLUG_JOIN)

        vs_ac_schemes = []
        for default, slug in ((True, ""), (False, "test-slug")):
            vs_ac_schemes.append(
                VoucherScheme.objects.create(
                    default=default,
                    slug=slug,
                    scheme=cls.scheme_accumulator,
                    barcode_type=1,
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
                    headline_pending="Voucher pending",
                    terms_and_conditions_url="https://example.com",
                    body_text_inprogress="voucher body",
                    body_text_issued="voucher body",
                    body_text_redeemed="voucher body",
                    body_text_expired="voucher body",
                    body_text_cancelled="voucher body",
                    body_text_pending="voucher body",
                )
            )

        cls.vs_accumulator, cls.vs_accumulator_2 = vs_ac_schemes

        cls.vs_stamps = VoucherScheme.objects.create(
            scheme=cls.scheme_stamps,
            barcode_type=1,
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
            headline_pending="Voucher pending",
            terms_and_conditions_url="https://example.com",
            body_text_inprogress="voucher body",
            body_text_issued="voucher body",
            body_text_redeemed="voucher body",
            body_text_expired="voucher body",
            body_text_cancelled="voucher body",
            body_text_pending="voucher body",
        )
        cls.vs_join = VoucherScheme.objects.create(
            scheme=cls.scheme_join,
            barcode_type=2,
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
            headline_pending="Voucher pending",
        )

    @staticmethod
    def voucher_resp(
        vs: VoucherScheme,
        state: str = VoucherStateStr.REDEEMED.value,
        value: int | float = 300,
        target_value: int | float = 400,
        issue_date: int | None = None,
        redeem_date: int | None = None,
        expiry_date: int | None = None,
    ) -> dict:
        now = arrow.utcnow().int_timestamp
        if not issue_date:
            issue_date = now
        if not expiry_date:
            expiry_date = now + 1000

        voucher = {
            "earn": {
                "type": "accumulator",
                "prefix": vs.earn_prefix,
                "suffix": vs.earn_suffix,
                "currency": vs.earn_currency,
                "value": value,
                "target_value": float(target_value),
            },
            "burn": {
                "type": vs.burn_type,
                "currency": vs.burn_currency,
                "prefix": vs.burn_prefix,
                "suffix": vs.burn_suffix,
                "value": vs.burn_value,
            },
            "code": "abc123",
            "date_issued": issue_date,
            "expiry_date": expiry_date,
            "headline": getattr(vs, f"headline_{state}"),
            "body_text": getattr(vs, f"body_text_{state}"),
            "subtext": "",
            "state": state,
            "barcode_type": vs.barcode_type,
            "terms_and_conditions_url": "https://example.com",
        }

        if state == VoucherStateStr.REDEEMED.value:
            voucher["date_redeemed"] = redeem_date or now + 1000
        if state == VoucherStateStr.ISSUED.value:
            voucher["headline"] = "£5.00 voucher earned"

        return voucher

    def test_accumulator_inprogress_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_accumulator_issued_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_accumulator_redeemed_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_accumulator_expired_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_accumulator_cancelled_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_accumulator_pending_headline(self):
        vs = self.vs_accumulator
        headline_template = vs.get_headline(vouchers.VoucherStateStr.PENDING)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher pending")

    def test_stamps_inprogress_headline(self):
        vs = self.vs_stamps
        headline_template = vs.get_headline(vouchers.VoucherStateStr.IN_PROGRESS)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£50.00 left to go!")

    def test_stamps_issued_headline(self):
        vs = self.vs_stamps
        headline_template = vs.get_headline(vouchers.VoucherStateStr.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_stamps_redeemed_headline(self):
        vs = self.vs_stamps
        headline_template = vs.get_headline(vouchers.VoucherStateStr.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_stamps_expired_headline(self):
        vs = self.vs_stamps
        headline_template = vs.get_headline(vouchers.VoucherStateStr.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_stamps_cancelled_headline(self):
        vs = self.vs_stamps
        headline_template = vs.get_headline(vouchers.VoucherStateStr.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_join_issued_headline(self):
        vs = self.vs_join
        headline_template = vs.get_headline(vouchers.VoucherStateStr.ISSUED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "£5.00 voucher earned")

    def test_join_redeemed_headline(self):
        vs = self.vs_join
        headline_template = vs.get_headline(vouchers.VoucherStateStr.REDEEMED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher redeemed")

    def test_join_expired_headline(self):
        vs = self.vs_join
        headline_template = vs.get_headline(vouchers.VoucherStateStr.EXPIRED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher expired")

    def test_join_cancelled_headline(self):
        vs = self.vs_join
        headline_template = vs.get_headline(vouchers.VoucherStateStr.CANCELLED)
        headline = vouchers.apply_template(headline_template, voucher_scheme=vs, earn_value=50, earn_target_value=100)
        self.assertEqual(headline, "Voucher cancelled")

    def test_make_voucher(self):
        now = arrow.utcnow().int_timestamp
        voucher_fields = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        vs: VoucherScheme = self.vs_accumulator
        account = SchemeAccount.objects.create(scheme=scheme, order=0)
        voucher = account.make_single_voucher(voucher_fields, vs)
        self.assertEqual(
            voucher,
            self.voucher_resp(
                vs,
                issue_date=voucher_fields["issue_date"],
                redeem_date=voucher_fields["redeem_date"],
                expiry_date=voucher_fields["expiry_date"],
            ),
        )

    def test_make_voucher_from_voucher_scheme_slug(self):
        now = arrow.utcnow().int_timestamp
        voucher_fields = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
            "voucher_scheme_slug": self.vs_accumulator_2.slug,
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        vs: VoucherScheme = self.vs_accumulator_2
        account = SchemeAccount.objects.create(scheme=scheme, order=0)
        voucher = account.make_single_voucher(voucher_fields, vs)
        self.assertEqual(
            voucher,
            self.voucher_resp(
                vs,
                issue_date=voucher_fields["issue_date"],
                redeem_date=voucher_fields["redeem_date"],
                expiry_date=voucher_fields["expiry_date"],
            ),
        )

    def test_make_voucher_sans_expiry_and_redeem_dates(self):
        now = arrow.utcnow().int_timestamp
        voucher_fields = {
            "issue_date": now,
            "code": "abc123",
            "value": 300,
            "target_value": 0,
            "state": VoucherStateStr.ISSUED.value,
            "expiry_date": arrow.get(now).shift(months=3).int_timestamp,
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        vs: VoucherScheme = self.vs_accumulator
        account = SchemeAccount.objects.create(scheme=scheme, order=0)
        voucher = account.make_single_voucher(voucher_fields, vs)

        self.assertEqual(
            voucher,
            self.voucher_resp(
                vs,
                state=VoucherStateStr.ISSUED.value,
                target_value=0,
                issue_date=voucher_fields["issue_date"],
                expiry_date=voucher_fields["expiry_date"],
            ),
        )

    def test_make_voucher_pending_conversion_date(self):
        # GIVEN
        now = arrow.utcnow().int_timestamp
        voucher_fields = {
            "issue_date": now,
            "code": "abc123",
            "value": 0,
            "target_value": 0,
            "state": VoucherStateStr.PENDING.value,
            "conversion_date": now,
            "expiry_date": arrow.get(now).shift(months=3).int_timestamp,
        }
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        vs: VoucherScheme = self.vs_accumulator
        account = SchemeAccount.objects.create(scheme=scheme, order=0)

        # WHEN
        voucher = account.make_single_voucher(voucher_fields, vs)

        # THEN
        voucher_resp = self.voucher_resp(
            vs,
            state=voucher_fields["state"],
            value=voucher_fields["value"],
            target_value=voucher_fields["target_value"],
            expiry_date=voucher_fields["expiry_date"],
            issue_date=voucher_fields["issue_date"],
        )
        voucher_resp["conversion_date"] = now
        self.assertEqual(
            voucher,
            voucher_resp,
        )

    def test_get_earn_target_value_from_voucher(self):
        """
        Test fetching the target value from the incoming voucher
        """
        # GIVEN
        vs = self.vs_stamps
        voucher_fields = {"target_value": 10}

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
        vs = self.vs_stamps
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
        vs = self.vs_stamps
        vs.earn_target_value = None
        voucher_fields = {}

        # THEN
        self.assertRaises(ValueError, vs.get_earn_target_value, voucher_fields)

    def test_get_earn_value_from_voucher_first(self):
        """
        Test getting the earn value from the incoming voucher, ahead of the earn_target_voucher
        """
        # GIVEN
        vs = self.vs_stamps
        expected_value = 8
        voucher_fields = {"value": expected_value}

        # WHEN
        earn_value = vs.get_earn_value(voucher_fields=voucher_fields, earn_target_value=12)

        # THEN
        self.assertEqual(expected_value, earn_value)

    def test_get_earn_value_assume_voucher_is_full(self):
        """
        Test that the earn value gets set to the earn target value, if the earn value is None.
        """
        # GIVEN
        vs = self.vs_stamps
        earn_target_value = 10
        voucher_fields = {
            "type": "stamps",
            "value": None,
        }

        # WHEN
        earn_value = vs.get_earn_value(voucher_fields=voucher_fields, earn_target_value=earn_target_value)

        # THEN
        self.assertEqual(earn_target_value, earn_value)

    def test_make_vouchers_response(self):
        now = arrow.utcnow().int_timestamp
        good_voucher_default = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
        }
        good_voucher_with_slug = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
            "voucher_scheme_slug": self.vs_accumulator_2.slug,
        }
        unrecognised_slug_voucher = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
            "voucher_scheme_slug": "bad-slug",
        }

        all_vouchers = [good_voucher_default, good_voucher_with_slug, unrecognised_slug_voucher]
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        account = SchemeAccount.objects.create(scheme=scheme, order=0)

        with mock.patch.object(logger, "error") as mock_error_log:
            vouchers_resp = account.make_vouchers_response(all_vouchers)

        self.assertTrue(mock_error_log.called)
        self.assertEqual(1, mock_error_log.call_count)
        self.assertListEqual(
            [
                self.voucher_resp(
                    self.vs_accumulator,
                    issue_date=good_voucher_default["issue_date"],
                    redeem_date=good_voucher_default["redeem_date"],
                    expiry_date=good_voucher_default["expiry_date"],
                ),
                self.voucher_resp(
                    self.vs_accumulator_2,
                    issue_date=good_voucher_with_slug["issue_date"],
                    redeem_date=good_voucher_with_slug["redeem_date"],
                    expiry_date=good_voucher_with_slug["expiry_date"],
                ),
            ],
            vouchers_resp,
        )

    def test_make_vouchers_response_no_default(self):
        self.vs_accumulator.default = False
        self.vs_accumulator.save(update_fields=["default"])

        now = arrow.utcnow().int_timestamp
        good_voucher_default = {
            "issue_date": now,
            "redeem_date": now,
            "expiry_date": now + 1000,
            "code": "abc123",
            "value": 300,
            "target_value": 400,
            "state": VoucherStateStr.REDEEMED.value,
        }

        all_vouchers = [good_voucher_default]
        scheme = Scheme.objects.get(slug=TEST_SLUG_ACCUMULATOR)
        account = SchemeAccount.objects.create(scheme=scheme, order=0)

        with mock.patch.object(logger, "error") as mock_error_log:
            vouchers_resp = account.make_vouchers_response(all_vouchers)

        self.assertTrue(mock_error_log.called)
        self.assertListEqual([], vouchers_resp)
