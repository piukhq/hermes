from django.apps import AppConfig


class MyAppConfig(AppConfig):
    name = 'ubiquity'
    verbose_name = "Ubiquity"

    def ready(self):
        from .influx_audit import InfluxAudit
        self.audit = InfluxAudit()
