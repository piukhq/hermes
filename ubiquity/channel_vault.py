import json
import logging
from enum import Enum

import requests
from requests.adapters import HTTPAdapter
from rest_framework import exceptions
from shared_config_storage.vault.secrets import VaultError, read_vault
from urllib3 import Retry

logger = logging.getLogger(__name__)
loaded = False
_bundle_secrets = {}
_secret_keys = {}


def retry_session(backoff_factor: float = 0.3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=backoff_factor,
        method_whitelist=False,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class SecretKeyName(str, Enum):
    PCARD_HASH_SECRET = "PCARD_HASH_SECRET"
    SPREEDLY_ENVIRONMENT_KEY = "SPREEDLY_ENVIRONMENT_KEY"
    SPREEDLY_ACCESS_SECRET = "SPREEDLY_ACCESS_SECRET"
    SPREEDLY_GATEWAY_TOKEN = "SPREEDLY_GATEWAY_TOKEN"


class KeyType(str, Enum):
    PRIVATE_KEY = "private_key"
    PUBLIC_KEY = "public_key"


def load_secrets(config):
    """
    Retrieves security credential values from channel and secret_keys storage vaults and stores them
    in _bundle_secrets and _secret_keys which are used as a cache.
    Secrets contained in _bundle_secrets and _secret_keys are bundle-specific.

    Example:

    _bundle_secrets = {
        "com.bink.wallet": {"key": "value"}
    }
    _secret_keys = {
        "PCARD_HASH_SECRET": "some secret"
    }


    """
    global loaded
    global _bundle_secrets
    global _secret_keys

    if loaded:
        logger.info("Tried to load the vault secrets more than once, ignoring the request.")

    elif config.get('LOCAL_CHANNEL_SECRETS'):
        logger.info(f"JWT bundle secrets - from local file {config['LOCAL_SECRETS_PATH']}")
        with open(config['LOCAL_SECRETS_PATH']) as fp:
            all_secrets = json.load(fp)

        _bundle_secrets = all_secrets['bundle_secrets']
        _secret_keys = all_secrets['secret_keys']
        loaded = True

    else:
        try:
            logger.info(
                f"JWT bundle secrets - from vault at {config['VAULT_URL']}  secrets: {config['CHANNEL_VAULT_PATH']}"
            )
            bundle_secrets = read_vault(config['CHANNEL_VAULT_PATH'], config['VAULT_URL'], config['VAULT_TOKEN'])
            logger.info(f"JWT bundle secrets - Found secrets for {[bundle_id for bundle_id in bundle_secrets]}")

        except requests.RequestException as e:
            err_msg = f"JWT bundle secrets - Vault Exception {e}"
            logger.exception(err_msg)
            raise VaultError(err_msg) from e

        try:
            logger.info(f"Loading secret keys from vault at {config['VAULT_URL']}")
            secret_keys = read_vault(config['SECRET_KEYS_VAULT_PATH'], config['VAULT_URL'], config['VAULT_TOKEN'])
        except requests.RequestException as e:
            err_msg = f"Secret keys - Vault Exception {e}"
            logger.exception(err_msg)
            raise VaultError(err_msg) from e

        _bundle_secrets = bundle_secrets
        _secret_keys = secret_keys
        loaded = True


def get_jwt_secret(bundle_id):
    try:
        return _bundle_secrets[bundle_id]['jwt_secret']
    except KeyError as e:
        raise exceptions.AuthenticationFailed(f"JWT is invalid: {e}") from e


def get_key(bundle_id, key_type: str):
    try:
        return _bundle_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e


def get_secret_key(secret: str):
    try:
        return _secret_keys[secret]
    except KeyError as e:
        err_msg = f"{e} not found in vault"
        logger.exception(err_msg)
        raise VaultError(err_msg)
