from typing import TYPE_CHECKING

from rest_framework import serializers
from rustyjeff import rsa_decrypt_base64
from shared_config_storage.credentials.encryption import BLAKE2sHash

from hermes.channel_vault import KeyType, get_secret_key, SecretKeyName, get_key
from scheme.models import SchemeContent, SchemeFee
from ubiquity.versioning.base import serializers as base_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme

ServiceConsentSerializer = base_serializers.ServiceConsentSerializer
PaymentCardSerializer = base_serializers.PaymentCardSerializer
TransactionSerializer = base_serializers.TransactionSerializer
MembershipCardSerializer = base_serializers.MembershipCardSerializer


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


class PaymentCardTranslationSerializer(base_serializers.PaymentCardTranslationSerializer):
    hash = serializers.SerializerMethodField()

    FIELDS_TO_DECRYPT = ['month', 'year', 'last_four_digits', 'first_six_digits', 'hash']

    @staticmethod
    def get_hash(obj: dict) -> str:
        return BLAKE2sHash().new(
            obj=obj["hash"],
            key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
        )

    def to_representation(self, data: dict) -> dict:
        values_to_decrypt = [data[key] for key in self.FIELDS_TO_DECRYPT]
        rsa_key_pem = get_key(
            bundle_id=self.context['bundle_id'],
            key_type=KeyType.PRIVATE_KEY
        )

        try:
            decrypted_values = zip(self.FIELDS_TO_DECRYPT, rsa_decrypt_base64(rsa_key_pem, values_to_decrypt))
        except ValueError as e:
            raise ValueError("Failed to decrypt sensitive fields") from e

        data.update(decrypted_values)
        return super().to_representation(data)
