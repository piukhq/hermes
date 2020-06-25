from typing import TYPE_CHECKING

from rest_framework import serializers
from shared_config_storage.credentials.encryption import BLAKE2sHash
from shared_config_storage.ubiquity.bin_lookup import bin_to_provider

from hermes.channel_vault import get_secret_key, SecretKeyName, decrypt_values_with_jeff, JeffDecryptionURL
from payment_card.models import PaymentCard
from scheme.models import SchemeContent, SchemeFee
from ubiquity.versioning.base import serializers as base_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme, SchemeAccount

ServiceConsentSerializer = base_serializers.ServiceConsentSerializer
PaymentCardSerializer = base_serializers.PaymentCardSerializer
TransactionSerializer = base_serializers.TransactionSerializer


class MembershipPlanContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeContent
        exclude = ('id', 'scheme')


class MembershipPlanFeeSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='fee_type')

    class Meta:
        model = SchemeFee
        exclude = ('id', 'scheme', 'fee_type')


class MembershipPlanSerializer(base_serializers.MembershipPlanSerializer):

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        plan['account']['fees'] = MembershipPlanFeeSerializer(instance.schemefee_set.all(), many=True).data
        plan['content'] = MembershipPlanContentSerializer(instance.schemecontent_set.all(), many=True).data

        has_vouchers = plan.pop('has_vouchers', False)
        plan['feature_set']['has_vouchers'] = has_vouchers

        return plan


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    def to_representation(self, instance: 'SchemeAccount') -> dict:
        card = super().to_representation(instance)

        # TODO: modify this to return actual fields once they have been implemented
        # if 'vouchers' in card:
        #     card['vouchers'].update({
        #         "body_text": "placeholder body text",
        #         "terms_and_conditions_url": "https://www.bink.com"
        #     })

        return card


class PaymentCardTranslationSerializer(base_serializers.PaymentCardTranslationSerializer):
    hash = serializers.SerializerMethodField()

    FIELDS_TO_DECRYPT = ['month', 'year', 'last_four_digits', 'first_six_digits', 'hash']

    def get_payment_card(self, obj: dict) -> list:
        slug = bin_to_provider(obj['first_six_digits'])
        return PaymentCard.objects.values_list('id', flat=True).get(slug=slug)

    @staticmethod
    def get_hash(obj: dict) -> str:
        return BLAKE2sHash().new(
            obj=obj["hash"],
            key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
        )

    def to_representation(self, data: dict) -> dict:
        values_to_decrypt = {key: data[key] for key in self.FIELDS_TO_DECRYPT}
        data.update(
            decrypt_values_with_jeff(JeffDecryptionURL.PAYMENT_CARD, self.context['bundle_id'], values_to_decrypt)
        )
        return super().to_representation(data)
