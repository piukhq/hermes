from django.apps import AppConfig


class MyAppConfig(AppConfig):

    name = 'daedalus_messaging'
    verbose_name = 'daedalus messaging'

    def ready(self):
        # import signal handlers
        import daedalus_messaging.signals
