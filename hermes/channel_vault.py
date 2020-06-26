import json
import logging
import sys
from enum import Enum

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from rest_framework import exceptions
from rest_framework.exceptions import ValidationError
from shared_config_storage.vault.secrets import VaultError, read_vault
from urllib3 import Retry

logger = logging.getLogger(__name__)


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


class JeffDecryptionURL(str, Enum):
    PAYMENT_CARD = settings.JEFF_URL + '/channel/{}/paymentcard'
    MEMBERSHIP_CARD = settings.JEFF_URL + '/channel/{}/membershipcard'


class ChannelVault:
    all_secrets = {}
    loaded = False

    def __init__(self, config):
        try:
            self.LOCAL_CHANNEL_SECRETS = config['LOCAL_CHANNEL_SECRETS']
            self.LOCAL_SECRETS_PATH = config['LOCAL_SECRETS_PATH']
            self.VAULT_URL = config['VAULT_URL']
            self.CHANNEL_VAULT_PATH = config['CHANNEL_VAULT_PATH']
            self.VAULT_TOKEN = config['VAULT_TOKEN']
            self.SECRET_KEYS_VAULT_PATH = config['SECRET_KEYS_VAULT_PATH']

            if config['TESTING'] is False and 'migrate' not in sys.argv:
                self._load_secrets()
                self.load_secrets_in_jeff()

        except KeyError as e:
            logger.exception(f"Failed to initialize ChannelVault - Vault Exception {e}")
            raise VaultError(f'Failed to initialize ChannelVault - Exception {e}') from e

    @property
    def bundle_secrets(self):
        return self.all_secrets["bundle_secrets"]

    @property
    def secret_keys(self):
        return self.all_secrets["secret_keys"]

    def load_secrets_in_jeff(self):
        session = retry_session(backoff_factor=2.5)
        base_url = settings.JEFF_URL + '/channel/{}/load'
        for channel, value in self.all_secrets['bundle_secrets'].items():
            if 'private_key' in value:
                try:
                    response = session.post(base_url.format(channel), json={'key': value['private_key']})
                    response.raise_for_status()
                except (requests.HTTPError, requests.RequestException) as e:
                    raise VaultError(f"Failed to load secrets into Jeff - Vault Exception {e}") from e

    def _load_secrets(self):
        """
        Retrieves security credential values from channel and secret_keys storage vaults and stored
        in _all_secrets which is used as a cache.
        Secrets contained in _all_secrets is separated by bundle-specific secrets and general secret keys.

        Example:
            _all_secrets = {
                "bundle_secrets": {
                    "com.bink.wallet": {"key": "value"}
                },
                "secret_keys": {
                    "PCARD_HASH_SECRET": "some secret"
                }
            }

        """

        if self.LOCAL_CHANNEL_SECRETS:
            logger.info(f"JWT bundle secrets - from local file {self.LOCAL_SECRETS_PATH}")
            with open(self.LOCAL_SECRETS_PATH) as fp:
                self.all_secrets = json.load(fp)

        else:
            try:
                logger.info(
                    f"JWT bundle secrets - from vault at {self.VAULT_URL}  secrets: {self.CHANNEL_VAULT_PATH}"
                )
                bundle_secrets = read_vault(self.CHANNEL_VAULT_PATH, self.VAULT_URL, self.VAULT_TOKEN)
                logger.info(f"JWT bundle secrets - Found secrets for {[bundle_id for bundle_id in bundle_secrets]}")

            except requests.RequestException as e:
                err_msg = f"JWT bundle secrets - Vault Exception {e}"
                logger.exception(err_msg)
                raise VaultError(err_msg) from e

            try:
                logger.info(f"Loading secret keys from vault at {self.VAULT_URL}")
                secret_keys = read_vault(self.SECRET_KEYS_VAULT_PATH, self.VAULT_URL, self.VAULT_TOKEN)
            except requests.RequestException as e:
                err_msg = f"Secret keys - Vault Exception {e}"
                logger.exception(err_msg)
                raise VaultError(err_msg) from e

            self.all_secrets["bundle_secrets"] = bundle_secrets
            self.all_secrets["secret_keys"] = secret_keys

        self.loaded = True


channel_vault = ChannelVault(settings.VAULT_CONFIG)


def get_jwt_secret(bundle_id):
    try:
        return channel_vault.bundle_secrets[bundle_id]['jwt_secret']
    except KeyError as e:
        raise exceptions.AuthenticationFailed(f"JWT is invalid: {e}") from e


def get_key(bundle_id, key_type: str):
    try:
        return channel_vault.bundle_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e


def get_secret_key(secret: str):
    try:
        return channel_vault.secret_keys[secret]
    except KeyError as e:
        err_msg = f"{e} not found in vault"
        logger.exception(err_msg)
        raise VaultError(err_msg)


def decrypt_values_with_jeff(base_url: JeffDecryptionURL, bundle_id: str, values: dict) -> dict:
    session = retry_session()
    url = base_url.value.format(bundle_id)
    try:
        response = session.post(url, json=values)
        # if jeff has been restarted we need to reload the keys
        if response.status_code == 412:
            channel_vault.load_secrets_in_jeff()
            response = session.post(url, json=values)

        response.raise_for_status()
    except (requests.HTTPError, requests.RequestException) as e:
        logger.exception(e)
        raise ValidationError('failed decryption of sensitive fields.')

    return response.json()
