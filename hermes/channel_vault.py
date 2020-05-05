import json
import logging
import sys
import typing as t
from enum import Enum

import requests
from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey
from django.conf import settings
from rest_framework import exceptions
from shared_config_storage.vault.secrets import VaultError, read_vault

logger = logging.getLogger(__name__)


class SecretKeyName(str, Enum):
    PCARD_HASH_SECRET = "PCARD_HASH_SECRET"
    SPREEDLY_ENVIRONMENT_KEY = "SPREEDLY_ENVIRONMENT_KEY"
    SPREEDLY_ACCESS_SECRET = "SPREEDLY_ACCESS_SECRET"
    SPREEDLY_GATEWAY_TOKEN = "SPREEDLY_GATEWAY_TOKEN"


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

        except KeyError as e:
            logger.exception(f"Failed to initialize ChannelVault - Vault Exception {e}")
            raise VaultError(f'Failed to initialize ChannelVault - Exception {e}') from e

    @property
    def bundle_secrets(self):
        return self.all_secrets["bundle_secrets"]

    @property
    def secret_keys(self):
        return self.all_secrets["secret_keys"]

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

                for bundle_id, secrets in bundle_secrets.items():
                    if 'private_key' in secrets:
                        bundle_secrets[bundle_id]['rsa_key'] = self._import_rsa_key(secrets['private_key'])

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

    @staticmethod
    def _import_rsa_key(extern_key: t.Union[str, bytes]) -> RsaKey:
        try:
            return RSA.import_key(extern_key)
        except (ValueError, IndexError, TypeError) as e:
            raise VaultError("Could not import private RSA key") from e


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
