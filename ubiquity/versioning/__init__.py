import logging
from enum import Enum
from typing import TYPE_CHECKING

from hermes.settings import Version, DEFAULT_API_VERSION
from ubiquity.versioning.base import serializers as base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers

if TYPE_CHECKING:
    from rest_framework.serializers import Serializer
    from rest_framework.request import Request

logger = logging.getLogger(__name__)

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


def get_api_version(request: 'Request') -> Version:
    if hasattr(request, 'api_version'):
        return request.api_version

    try:
        ver = "{}.{}".format(*request.version.split('.')[:2])
        ver = Version(ver).value

    except (IndexError, ValueError) as e:
        if e.__class__ is ValueError:
            message = f"Unknown version found in accept header: {ver}, "
        else:
            message = f"Unknown version format in accept header, "

        logger.debug(message + f"defaulting the max version: {DEFAULT_API_VERSION}")
        ver = DEFAULT_API_VERSION

    setattr(request, 'api_version', ver)
    return ver


def versioned_serializer_class(request: 'Request', model: SelectSerializer) -> 'Serializer':
    version = get_api_version(request)
    serializers = SERIALIZERS_CLASSES[version]
    return getattr(serializers, model)
