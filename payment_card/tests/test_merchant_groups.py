from django.test import TestCase

from payment_card.models import VopMerchantGroup


class TestVopMerchantGroups(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.default_group = VopMerchantGroup.objects.get(default=True)
        cls.non_default_group = VopMerchantGroup(offer_id=12345, group_name="Test Group")
        cls.non_default_group.save()
        VopMerchantGroup.cached_group_lookup.cache_clear()

    def test_cached_group_lookup_ok(self) -> None:
        for msg, requested_group_id, expected_returned_group in (
            ("default group by id", self.default_group.id, self.default_group),
            ("group non specified returns default group", None, self.default_group),
            ("non default group by id", self.non_default_group.id, self.non_default_group),
        ):
            with self.subTest(
                msg, requested_group_id=requested_group_id, expected_returned_group=expected_returned_group
            ):
                merchant_group = VopMerchantGroup.cached_group_lookup(requested_group_id)
                self.assertEquals(merchant_group, expected_returned_group)

    def test_cached_group_lookup_not_found(self) -> None:
        self.assertRaises(VopMerchantGroup.DoesNotExist, VopMerchantGroup.cached_group_lookup, -1)
