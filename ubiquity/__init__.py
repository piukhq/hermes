from django.apps import AppConfig
from django.conf import settings


class MyAppConfig(AppConfig):
    name = 'ubiquity'
    verbose_name = "Ubiquity"

    def ready(self):
        if settings.USE_INFLUXDB:
            from .influx_audit import InfluxAudit
            self.audit = InfluxAudit()
