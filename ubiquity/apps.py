from django.apps import AppConfig
from django.conf import settings

from ubiquity.channel_vault import load_secrets, logger


class UbiquityConfig(AppConfig):
    name = "ubiquity"
    verbose_name = "Ubiquity"

    def ready(self):
        if settings.INIT_RUNTIME_APPS:
            load_secrets(settings.VAULT_CONFIG)
        else:
            logger.info("Vault not initialised as this is either a test, a migration, or statics collection")
