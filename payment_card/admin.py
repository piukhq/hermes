from django.contrib import admin
from payment_card.models import Issuer, PaymentCardAccount, PaymentCard, PaymentAccountImageCriteria, \
    PaymentCardAccountImage

admin.site.register(Issuer)
admin.site.register(PaymentCardAccount)
admin.site.register(PaymentCard)
admin.site.register(PaymentCardAccountImage)
admin.site.register(PaymentAccountImageCriteria)
