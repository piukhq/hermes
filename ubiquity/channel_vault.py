import json
import logging
from enum import Enum

import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from requests.adapters import HTTPAdapter
from rest_framework import exceptions
from urllib3 import Retry

logger = logging.getLogger(__name__)
loaded = False
_bundle_secrets = {}
_secret_keys = {}
_aes_keys = {}


class VaultError(Exception):
    """Exception raised for errors in the input."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"Vault Error: {self.message}"


def retry_session(backoff_factor: float = 0.3) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=backoff_factor, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class AESKeyNames(str, Enum):
    AES_KEY = "AES_KEY"
    LOCAL_AES_KEY = "LOCAL_AES_KEY"


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
    global _aes_keys

    if loaded:
        logger.info("Tried to load the vault secrets more than once, ignoring the request.")

    elif config.get("LOCAL_SECRETS"):
        logger.info(f"Fetching secrets from local file: {config['LOCAL_SECRETS_PATH']}")
        with open(config["LOCAL_SECRETS_PATH"]) as fp:
            local_secrets = json.load(fp)

        _bundle_secrets = local_secrets["channels"]
        _secret_keys = local_secrets["secret-keys"]
        _aes_keys = local_secrets["aes-keys"]
        loaded = True

    else:
        secrets_to_load = [
            (config["SECRET_KEYS_NAME"], _secret_keys),
            (config["AES_KEYS_NAME"], _aes_keys),
        ]

        client = get_azure_client(config)

        #  Fetch channel information from all secrets with prefix 'ubiquity-channel-'
        all_secrets_in_vault = client.list_properties_of_secrets()
        for secret in all_secrets_in_vault:
            if "ubiquity-channel" in secret.name:
                secret_definition = (secret.name, _bundle_secrets)
                secrets_to_load.append(secret_definition)
                logger.info(f"Found channel information: {secret.name} - adding to load list")

        errors = []
        failed_secrets = []
        for secret_name, secret_dict in secrets_to_load:
            try:
                logger.info(f"Loading {secret_name} from vault at {config['VAULT_URL']}")
                secret_dict.update(json.loads(client.get_secret(secret_name).value))
                logger.info(f"Success: Loaded {secret_name}")

            except Exception as e:
                failed_secrets.append(secret_name)
                errors.append(f"Exception {e}")

        if errors:
            err_msg = "Failed to load secrets: "
            logger.exception(
                "{}\n{}".format(
                    err_msg,
                    "\n".join([str(obj) for obj in zip(failed_secrets, errors, strict=False)]),
                )
            )
            raise VaultError(f"{failed_secrets}")

        loaded = True


def get_azure_client(config: dict) -> SecretClient:
    credential = DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_shared_token_cache_credential=True,
        exclude_visual_studio_code_credential=True,
        exclude_interactive_browser_credential=True,
    )

    return SecretClient(vault_url=config["VAULT_URL"], credential=credential)


def get_jwt_secret(bundle_id):
    try:
        return _bundle_secrets[bundle_id]["jwt_secret"]
    except KeyError as e:
        raise exceptions.AuthenticationFailed("JWT is invalid") from e


def get_bundle_key(bundle_id, key_type: str):
    try:
        return _bundle_secrets[bundle_id][key_type]
    except KeyError as e:
        raise VaultError(f"Unable to locate {key_type} in vault for bundle {bundle_id}") from e


def get_secret_key(secret_key_name: str):
    try:
        return _secret_keys[secret_key_name]
    except KeyError as exc:
        err_msg = f"{secret_key_name} not found in vault"
        logger.exception(err_msg)
        raise VaultError(err_msg) from exc


def get_aes_key(key_type: str):
    try:
        return _aes_keys[key_type]
    except KeyError as exc:
        err_msg = f"{key_type} not found in _aes_keys."
        logger.exception(err_msg)
        raise VaultError(err_msg) from exc
