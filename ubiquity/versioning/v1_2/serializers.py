from typing import TYPE_CHECKING

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
TransactionsSerializer = base_serializers.TransactionsSerializer


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
    pan_start = serializers.SerializerMethodField()
    pan_end = serializers.SerializerMethodField()
    expiry_year = serializers.SerializerMethodField()
    expiry_month = serializers.SerializerMethodField()
    hash = serializers.SerializerMethodField()

    def get_payment_card(self, obj):
        pan_start = self.context.get('decrypted_pan_start')
        if not pan_start:
            pan_start = self._decrypt_val(obj['first_six_digits'])
            self.context['decrypted_pan_start'] = pan_start
        slug = bin_to_provider(pan_start)
        return PaymentCard.objects.values('id').get(slug=slug)['id']

    def get_pan_start(self, obj):
        # pan_start stored in context so it is only decrypted once as it is also used
        # in get_payment_card
        pan_start = self.context.get('decrypted_pan_start')
        if not pan_start:
            pan_start = self._decrypt_val(obj['first_six_digits'])
            self.context['decrypted_pan_start'] = pan_start
        return pan_start

    def get_pan_end(self, obj):
        return self._decrypt_val(obj['last_four_digits'])

    def get_expiry_year(self, obj):
        return int(self._decrypt_val(obj['year']))

    def get_expiry_month(self, obj):
        return int(self._decrypt_val(obj['month']))

    def get_hash(self, obj):
        hash1 = self._decrypt_val(obj["hash"])
        hash2 = BLAKE2sHash().new(
            obj=hash1,
            key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
        )
        return hash2

    def _decrypt_val(self, val):
        if not self.context.get('rsa'):
            self.context['rsa'] = RSACipher()

        key = get_key(bundle_id=self.context['bundle_id'], key_type='private_key')
        rsa = self.context['rsa']
        return rsa.decrypt(val, priv_key=key)
