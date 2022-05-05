from django.apps import AppConfig


class SchemeAppConfig(AppConfig):
    name = "scheme"
    verbose_name = "Scheme"

    def ready(self):
        import scheme.signals  # noqa
