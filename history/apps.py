from django.apps import AppConfig


class HistoryConfig(AppConfig):
    name = 'history'

    def ready(self):
        # import signal handlers - THIS IS NOT AN ERROR
        import history.signals  # noqa: F401
