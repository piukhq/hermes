from django.contrib import admin

from payment_card import models


class PaymentCardImageInline(admin.StackedInline):
    model = models.PaymentCardImage
    extra = 0


class PaymentCardAdmin(admin.ModelAdmin):
    inlines = (PaymentCardImageInline,)
    list_display = ('name', 'id', 'is_active',)
    list_filter = ('is_active', )


def titled_filter(title):
    class Wrapper(admin.RelatedFieldListFilter):

        def __new__(cls, *args, **kwargs):
            instance = admin.RelatedFieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance
    return Wrapper


class PaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'payment_card', 'pan_start', 'pan_end', 'is_deleted', 'created',)
    list_filter = (('payment_card__name', titled_filter('payment card')),
                   'status',
                   ('issuer__name', titled_filter('issuer')),
                   'is_deleted',)
    readonly_fields = ('token',)
    search_fields = ['user__email', 'pan_start', 'pan_end', 'token']


class PaymentCardAccountImageAdmin(admin.ModelAdmin):
    list_display = ('description', 'status', 'payment_card', 'start_date', 'end_date', 'created',)
    list_filter = ('status', 'start_date', 'end_date', 'payment_card',)
    date_hierarchy = 'start_date'
    raw_id_fields = ('payment_card_accounts',)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class ProviderStatusMappingAdmin(admin.ModelAdmin):
    list_display = ('provider', 'provider_status_code', 'bink_status_code')
    list_filter = ('provider', 'bink_status_code')
    search_fields = ('provider_status_code', 'bink_status_code')


admin.site.register(models.Issuer)
admin.site.register(models.PaymentCardAccount, PaymentCardAccountAdmin)
admin.site.register(models.PaymentCard, PaymentCardAdmin)
admin.site.register(models.PaymentCardAccountImage, PaymentCardAccountImageAdmin)
admin.site.register(models.ProviderStatusMapping, ProviderStatusMappingAdmin)
