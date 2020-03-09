import logging
from enum import Enum
from typing import TYPE_CHECKING

from ubiquity.versioning.base import serializers as base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers

if TYPE_CHECKING:
    from rest_framework.serializers import Serializer

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


def versioned_serializer_class(version: Version, model: SelectSerializer) -> 'Serializer':
    # we normalise version number in the accept_version middleware, if somehow we get the wrong version here it's a bug
    serializers = SERIALIZERS_CLASSES[version]
    return getattr(serializers, model)
