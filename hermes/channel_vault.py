import json
import logging
import sys

import requests
from Crypto.PublicKey import RSA
from django.conf import settings
from rest_framework import exceptions
from shared_config_storage.vault.secrets import VaultError, read_vault

logger = logging.getLogger(__name__)


class ChannelVault:
    bundle_secrets = {}
    loaded = False

    def __init__(self, config):
        try:
            self.LOCAL_CHANNEL_SECRETS = config['LOCAL_CHANNEL_SECRETS']
            self.LOCAL_SECRETS_PATH = config['LOCAL_SECRETS_PATH']
            self.VAULT_URL = config['VAULT_URL']
            self.CHANNEL_VAULT_PATH = config['CHANNEL_VAULT_PATH']
            self.VAULT_TOKEN = config['VAULT_TOKEN']
            self.PCARD_HASH_SECRET_PATH = config['PCARD_HASH_SECRET_PATH']
            if config['TESTING'] is False and 'migrate' not in sys.argv:
                self._load_bundle_secrets()

        except KeyError as e:
            logger.exception(f"Failed to initialize ChannelVault - Vault Exception {e}")
            raise VaultError(f'Failed to initialize ChannelVault - Exception {e}') from e

    def _load_bundle_secrets(self) -> None:
        """
        On startup retrieves security credential values from channel secrets storage vault.
        The returned record from read vault returns all data for every bundle from which jwt_secret is extracted

        data is passed into _bundle_secrets which is used as a cache for API authentication by bundle

        """

        if self.LOCAL_CHANNEL_SECRETS:
            logger.info(f"JWT bundle secrets - from local file {self.LOCAL_SECRETS_PATH}")
            with open(self.LOCAL_SECRETS_PATH) as fp:
                self.bundle_secrets = json.load(fp)

        else:
            logger.info(
                f"JWT bundle secrets - from vault at {self.VAULT_URL}  secrets: {self.CHANNEL_VAULT_PATH}"
            )
            print(f"JWT bundle secrets - from vault at {self.VAULT_URL}  secrets: {self.CHANNEL_VAULT_PATH}")

            try:
                record = read_vault(self.CHANNEL_VAULT_PATH, self.VAULT_URL, self.VAULT_TOKEN)
            except requests.RequestException as e:
                logger.exception(f"JWT bundle secrets - Vault Exception {e}")
                raise VaultError(f'JWT bundle secrets - Exception {e}') from e

            for bundle_id, secret in record.items():
                self.bundle_secrets[bundle_id] = secret
                if 'private_key' in secret:
                    self.bundle_secrets[bundle_id]['rsa_key'] = RSA.import_key(secret['private_key'])

            logger.info(f"Payment Card hash secret - from vault at {self.VAULT_URL}")
            try:
                hash_secret = read_vault(self.PCARD_HASH_SECRET_PATH, self.VAULT_URL, self.VAULT_TOKEN)
            except requests.RequestException as e:
                logger.exception(f"Payment Card hash secret - Vault Exception {e}")
                raise VaultError(f'Payment Card hash secret - Exception {e}') from e
            self.bundle_secrets["pcard_hash_secret"] = hash_secret['data']['salt']

        logger.info(f"JWT bundle secrets - Found secrets for {[bundle_id for bundle_id in self.bundle_secrets]}")
        self.loaded = True


channel_vault = ChannelVault(settings.VAULT_CONFIG)


def get_jwt_secret(bundle_id):
    try:
        return channel_vault.bundle_secrets[bundle_id]['jwt_secret']
    except KeyError as e:
        raise exceptions.AuthenticationFailed(f"JWT is invalid: {e}") from e


def get_pcard_hash_secret():
    try:
        return channel_vault.bundle_secrets["pcard_hash_secret"]
    except KeyError as e:
        raise VaultError("Unable to locate pcard_hash_secret in vault") from e


def get_key(bundle_id, key_type: str):
    try:
        return channel_vault.bundle_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e
