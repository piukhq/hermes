from django.apps import AppConfig


class PaymentCardAppConfig(AppConfig):
    name = "payment_card"
    verbose_name = "Payment card"

    def ready(self):
        import payment_card.signals  # noqa
