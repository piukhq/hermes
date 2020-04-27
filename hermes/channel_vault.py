import json
import logging
from enum import Enum

import requests
from django.conf import settings
from rest_framework import exceptions
from shared_config_storage.vault.secrets import VaultError, read_vault

_all_secrets = {}
loaded = False

logger = logging.getLogger(__name__)


class SecretKeyName(str, Enum):
    PCARD_HASH_SECRET = "PCARD_HASH_SECRET"
    SPREEDLY_ENVIRONMENT_KEY = "SPREEDLY_ENVIRONMENT_KEY"
    SPREEDLY_ACCESS_SECRET = "SPREEDLY_ACCESS_SECRET"
    SPREEDLY_GATEWAY_TOKEN = "SPREEDLY_GATEWAY_TOKEN"


def load_secrets():
    """
    On startup retrieves security credential values from channel secrets storage vault.
    The returned record from read vault returns all data for every bundle from which jwt_secret is extracted

    data is passed into _bundle_secrets which is used as a cache for API authentication by bundle

    """
    global _all_secrets
    global loaded

    if settings.LOCAL_CHANNEL_SECRETS:
        logger.info(f"JWT bundle secrets - from local file {settings.LOCAL_SECRETS_PATH}")
        with open(settings.LOCAL_SECRETS_PATH) as fp:
            _all_secrets = json.load(fp)

    else:
        logger.info(
            f"JWT bundle secrets - from vault at {settings.VAULT_URL}  secrets: {settings.CHANNEL_VAULT_PATH}"
        )

        try:
            record = read_vault(settings.CHANNEL_VAULT_PATH, settings.VAULT_URL, settings.VAULT_TOKEN)
        except requests.RequestException as e:
            err_msg = f"JWT bundle secrets - Vault Exception {e}"
            logger.exception(err_msg)
            raise VaultError(err_msg) from e
        bundle_secrets = {bundle_id: secret for bundle_id, secret in record.items()}
        logger.info(f"JWT bundle secrets - Found secrets for {[bundle_id for bundle_id in _all_secrets]}")

        logger.info(f"Loading secret keys from vault at {settings.VAULT_URL}")
        try:
            secret_keys = read_vault(settings.SECRET_KEYS_PATH, settings.VAULT_URL, settings.VAULT_TOKEN)
        except requests.RequestException as e:
            err_msg = f"Secret keys - Vault Exception {e}"
            logger.exception(err_msg)
            raise VaultError(err_msg) from e

        _all_secrets["bundle_secrets"] = bundle_secrets
        _all_secrets["secret_keys"] = secret_keys

    loaded = True


def get_jwt_secret(bundle_id):
    try:
        if not loaded:
            load_secrets()

        return _all_secrets["bundle_secrets"][bundle_id]["jwt_secret"]
    except KeyError as e:
        raise exceptions.AuthenticationFailed(f"JWT is invalid: {e}") from e


def get_key(bundle_id, key_type: str):
    try:
        if not loaded:
            load_secrets()

        return _all_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e


def get_secret_key(secret: str):
    try:
        if not loaded:
            load_secrets()

        return _all_secrets["secret_keys"][secret]
    except KeyError as e:
        err_msg = f"{e} not found in vault"
        logger.exception(err_msg)
        raise VaultError(err_msg)

