import logging
from enum import Enum

from ubiquity.base import serializers as base_serializers
from ubiquity.v1_2 import serializers as v1_2_serializers

logger = logging.getLogger(__name__)


class Version(str, Enum):
    v1_0 = '1.0'
    v1_1 = '1.1'
    v1_2 = '1.2'


MAX_VERSION = Version.v1_2
SERIALIZERS_CLASSES = {
    Version.v1_0: base_serializers,
    Version.v1_1: base_serializers,
    Version.v1_2: v1_2_serializers
}


class SelectSerializer(str, Enum):
    SERVICE = 'ServiceConsentSerializer'
    MEMBERSHIP_PLAN = 'MembershipPlanSerializer'
    MEMBERSHIP_CARD = 'MembershipCardSerializer'
    PAYMENT_CARD = 'PaymentCardSerializer'
    MEMBERSHIP_TRANSACTION = 'TransactionsSerializer'


def versioned_serializer_class(version: Version, model: SelectSerializer):
    try:
        serializers = SERIALIZERS_CLASSES[version]
    except (KeyError, TypeError):
        logger.debug(f"Unknown version found in accept header: {version}, "
                     f"defaulting the max version: {MAX_VERSION}")
        serializers = SERIALIZERS_CLASSES[MAX_VERSION]

    return getattr(serializers, model)
