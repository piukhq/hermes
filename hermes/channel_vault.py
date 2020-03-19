import json
import logging

import requests
from rest_framework import exceptions
from shared_config_storage.vault.secrets import VaultError, read_vault

from django.conf import settings

_bundle_secrets = {}
loaded = False

logger = logging.getLogger(__name__)


def load_bundle_secrets():
    """
    On startup retrieves security credential values from channel secrets storage vault.
    The returned record from read vault returns all data for every bundle from which jwt_secret is extracted

    data is passed into _bundle_secrets which is used as a cache for API authentication by bundle

    """
    global _bundle_secrets
    global loaded

    if settings.LOCAL_CHANNEL_SECRETS:
        logger.info(f"JWT bundle secrets - from local file {settings.LOCAL_SECRETS_PATH}")
        with open(settings.LOCAL_SECRETS_PATH) as fp:
            _bundle_secrets = json.load(fp)

    else:
        logger.info(
            f"JWT bundle secrets - from vault at {settings.VAULT_URL}  secrets: {settings.CHANNEL_VAULT_PATH}"
        )
        print(f"JWT bundle secrets - from vault at {settings.VAULT_URL}  secrets: {settings.CHANNEL_VAULT_PATH}")

        try:
            record = read_vault(settings.CHANNEL_VAULT_PATH, settings.VAULT_URL, settings.VAULT_TOKEN)
        except requests.RequestException as e:
            logger.exception(f"JWT bundle secrets - Vault Exception {e}")
            raise VaultError(f'JWT bundle secrets - Exception {e}') from e
        _bundle_secrets = {bundle_id: secret for bundle_id, secret in record.items()}

        logger.info(f"Payment Card hash secret - from vault at {settings.VAULT_URL}")
        try:
            hash_secret = read_vault(settings.PCARD_HASH_SECRET_PATH, settings.VAULT_URL, settings.VAULT_TOKEN)
        except requests.RequestException as e:
            logger.exception(f"Payment Card hash secret - Vault Exception {e}")
            raise VaultError(f'Payment Card hash secret - Exception {e}') from e
        _bundle_secrets["pcard_hash_secret"] = hash_secret['data']['salt']

    logger.info(f"JWT bundle secrets - Found secrets for {[bundle_id for bundle_id in _bundle_secrets]}")
    loaded = True


def get_jwt_secret(bundle_id):
    try:
        if not loaded:
            load_bundle_secrets()

        return _bundle_secrets[bundle_id]['jwt_secret']
    except KeyError as e:
        raise exceptions.AuthenticationFailed(f"JWT is invalid: {e}") from e


def get_pcard_hash_secret():
    try:
        if not loaded:
            load_bundle_secrets()

        return _bundle_secrets["pcard_hash_secret"]
    except KeyError as e:
        raise VaultError("Unable to locate pcard_hash_secret in vault") from e


def get_key(bundle_id, key_type: str):
    try:
        if not loaded:
            load_bundle_secrets()

        return _bundle_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e
