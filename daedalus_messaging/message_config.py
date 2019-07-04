from django.apps import AppConfig


class MessageAppConfig(AppConfig):

    name = 'daedalus_messaging'
    verbose_name = 'daedalus messaging'

    def ready(self):
        # import signal handlers
        import daedalus_messaging.signals
