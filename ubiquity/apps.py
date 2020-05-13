from django.apps import AppConfig

from hermes.channel_vault import init_vault


class UbiquityConfig(AppConfig):
    name = 'ubiquity'
    verbose_name = 'Ubiquity'

    def ready(self):
        init_vault()
