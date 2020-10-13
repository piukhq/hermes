import logging
from os.path import join
from typing import TYPE_CHECKING

from django.conf import settings

from ubiquity.versioning import base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme, SchemeAccount

logger = logging.getLogger(__name__)

ServiceConsentSerializer = v1_2_serializers.ServiceConsentSerializer
PaymentCardSerializer = v1_2_serializers.PaymentCardSerializer
TransactionSerializer = v1_2_serializers.TransactionSerializer
PaymentCardTranslationSerializer = v1_2_serializers.PaymentCardTranslationSerializer


def _add_base_media_url_with_dark_mode(image: dict) -> dict:
    if settings.NO_AZURE_STORAGE:
        base_url = settings.MEDIA_URL
    else:
        base_url = settings.AZURE_CUSTOM_DOMAIN

    images = {
        **image,
        'url': join(base_url, image['url']),
    }

    if image.get('dark_mode_url'):
        images['dark_mode_url'] = join(base_url, images['dark_mode_url'])

    return images


class MembershipPlanSerializer(v1_2_serializers.MembershipPlanSerializer):

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        plan["card"]["secondary_colour"] = instance.secondary_colour
        return plan


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    def to_representation(self, instance: 'SchemeAccount') -> dict:
        scheme_account = super().to_representation(instance)

        if settings.NO_AZURE_STORAGE:
            base_url = settings.MEDIA_URL
        else:
            base_url = settings.AZURE_CUSTOM_DOMAIN

        images = scheme_account['images']

        for image in images:
            if image.get('dark_mode_url'):
                image['dark_mode_url'] = join(base_url, image['dark_mode_url'])
            else:
                continue

        scheme_account['images'] = images
        return scheme_account
