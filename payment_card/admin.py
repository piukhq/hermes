from django.contrib import admin
from payment_card.models import Issuer, PaymentCardAccount, PaymentCard, PaymentAccountImageCriteria, \
    PaymentCardAccountImage


class PaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'payment_card', 'pan_start', 'pan_end', 'is_deleted')


class PaymentAccountImageCriteriaAdmin(admin.ModelAdmin):
    model = PaymentAccountImageCriteria
    filter_horizontal = ('payment_card_accounts',)


admin.site.register(Issuer)
admin.site.register(PaymentCardAccount, PaymentCardAccountAdmin)
admin.site.register(PaymentCard)
admin.site.register(PaymentCardAccountImage)
admin.site.register(PaymentAccountImageCriteria, PaymentAccountImageCriteriaAdmin)
