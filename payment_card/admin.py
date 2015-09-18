from django.contrib import admin
from payment_card.models import Issuer, PaymentCardAccount, PaymentCard

admin.site.register(Issuer)
admin.site.register(PaymentCardAccount)
admin.site.register(PaymentCard)