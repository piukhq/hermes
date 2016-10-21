from django.contrib import admin
from payment_card.models import Issuer, PaymentCardAccount, PaymentCard, PaymentCardAccountImage, PaymentCardImage


class PaymentCardImageInline(admin.StackedInline):
    model = PaymentCardImage
    extra = 0


class PaymentCardAdmin(admin.ModelAdmin):
    inlines = (PaymentCardImageInline,)
    list_display = ('name', 'id', 'is_active')
    list_filter = ('is_active', )


def titled_filter(title):
    class Wrapper(admin.RelatedFieldListFilter):

        def __new__(cls, *args, **kwargs):
            instance = admin.RelatedFieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance
    return Wrapper


class PaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'payment_card', 'pan_start', 'pan_end', 'is_deleted')
    list_filter = (('payment_card__name', titled_filter('payment card')),
                   'status',
                   ('issuer__name', titled_filter('issuer')),
                   'is_deleted',)
    readonly_fields = ('token',)
    search_fields = ['user__email', 'pan_start', 'pan_end', 'token']


class PaymentCardAccountImageAdmin(admin.ModelAdmin):
    list_display = ('description', 'status', 'payment_card', 'start_date', 'end_date')
    list_filter = ('status', 'start_date', 'end_date', 'payment_card')
    date_hierarchy = 'start_date'
    filter_horizontal = ('payment_card_accounts',)


admin.site.register(Issuer)
admin.site.register(PaymentCardAccount, PaymentCardAccountAdmin)
admin.site.register(PaymentCard, PaymentCardAdmin)
admin.site.register(PaymentCardAccountImage, PaymentCardAccountImageAdmin)
