from typing import Union, ValuesView

from django.conf import settings


def needs_decryption(values: Union[list, ValuesView]) -> bool:
    return all(
        map(
            lambda x: isinstance(x, str) and len(x) > settings.ENCRYPTED_VALUES_LENGTH_CONTROL,
            values,
        )
    )
