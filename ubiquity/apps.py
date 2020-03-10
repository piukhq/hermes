from django.apps import AppConfig

from hermes.channel_vault import load_bundle_secrets


class UbiquityConfig(AppConfig):
    name = 'ubiquity'

    # def ready(self):
    #     load_bundle_secrets()
