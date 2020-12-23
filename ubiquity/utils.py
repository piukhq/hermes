from typing import Iterable

from django.conf import settings


def needs_decryption(values: Iterable) -> bool:
    return all(
        map(
            lambda x: isinstance(x, str) and len(x) > settings.ENCRYPTED_VALUES_LENGTH_CONTROL,
            values,
        )
    )
