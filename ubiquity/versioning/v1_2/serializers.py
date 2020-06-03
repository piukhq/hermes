from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework import serializers
from shared_config_storage.credentials.encryption import BLAKE2sHash, RSACipher
from shared_config_storage.ubiquity.bin_lookup import bin_to_provider

from hermes.channel_vault import get_key, get_secret_key, SecretKeyName
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
    pool_executor = ProcessPoolExecutor(max_workers=settings.POOL_EXECUTOR_MAX_WORKERS)
    rsa_cipher = RSACipher()

    def get_payment_card(self, obj):
        slug = bin_to_provider(obj['first_six_digits'])
        return PaymentCard.objects.values_list('id', flat=True).get(slug=slug)

    @staticmethod
    def get_hash(obj):
        return BLAKE2sHash().new(
            obj=obj["hash"],
            key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
        )

    @staticmethod
    def _decrypt_val(rsa_cipher, bundle_id, val):
        rsa_key = get_key(bundle_id=bundle_id, key_type='rsa_key')
        return rsa_cipher.decrypt(val, rsa_key=rsa_key)

    def to_representation(self, data):
        values = [data[key] for key in self.FIELDS_TO_DECRYPT]
        decrypt_val = partial(self._decrypt_val, self.rsa_cipher, self.context['bundle_id'])
        data.update(zip(self.FIELDS_TO_DECRYPT, self.pool_executor.map(decrypt_val, values)))
        return super().to_representation(data)
