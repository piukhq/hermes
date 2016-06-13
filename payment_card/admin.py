from django.contrib import admin
from payment_card.models import (Issuer, PaymentCardAccount, PaymentCard, PaymentCardAccountImage, PaymentCardImage,
                                 PaymentCardAccountImageCriteria)


class PaymentCardImageInline(admin.StackedInline):
    model = PaymentCardImage
    extra = 0


class PaymentCardAdmin(admin.ModelAdmin):
    inlines = (PaymentCardImageInline,)
    list_display = ('name', 'id', 'is_active')
    list_filter = ('is_active', )


class PaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'payment_card', 'pan_start', 'pan_end', 'is_deleted')


class PaymentAccountImageCriteriaAdmin(admin.ModelAdmin):
    model = PaymentCardAccountImageCriteria
    filter_horizontal = ('payment_card_accounts',)


admin.site.register(Issuer)
admin.site.register(PaymentCardAccount, PaymentCardAccountAdmin)
admin.site.register(PaymentCard, PaymentCardAdmin)
admin.site.register(PaymentCardAccountImage)
admin.site.register(PaymentCardAccountImageCriteria, PaymentAccountImageCriteriaAdmin)
