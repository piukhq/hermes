import arrow
from django.contrib import admin
from django.utils.html import format_html
from ubiquity.models import PaymentCardAccountEntry
from payment_card import models


@admin.register(models.PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'is_active',)
    list_filter = ('is_active',)


@admin.register(models.PaymentCardImage)
class PaymentCardImageAdmin(admin.ModelAdmin):
    list_display = ('payment_card', 'description', 'status', 'start_date', 'end_date', 'created',)
    list_filter = ('payment_card', 'status', 'created',)
    search_fields = ('payment_card__name', 'description')
    raw_id_fields = ('payment_card',)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


def titled_filter(title):
    class Wrapper(admin.RelatedFieldListFilter):

        def __new__(cls, *args, **kwargs):
            instance = admin.RelatedFieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance

    return Wrapper


@admin.register(models.PaymentCardAccount)
class PaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ('payment_card', 'pan_start', 'pan_end', 'is_deleted', 'created',)
    list_filter = (('payment_card__name', titled_filter('payment card')),
                   'status',
                   ('issuer__name', titled_filter('issuer')),
                   'is_deleted',)
    readonly_fields = ('token', 'psp_token', 'PLL_consent')
    search_fields = ['pan_start', 'pan_end', 'token']
    exclude = ('consent',)

    def PLL_consent(self, obj):
        when = arrow.get(obj.consent['timestamp']).format('HH:mm DD/MM/YYYY')
        return 'Date Time: {} \nCoordinates: {}, {}'.format(when, obj.consent['latitude'], obj.consent['longitude'])


@admin.register(models.PaymentCardAccountImage)
class PaymentCardAccountImageAdmin(admin.ModelAdmin):
    list_display = ('payment_card', 'description', 'status', 'start_date', 'end_date', 'created',)
    list_filter = ('payment_card', 'status', 'created',)
    search_fields = ('payment_card__name', 'description')
    raw_id_fields = ('payment_card_accounts',)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(models.ProviderStatusMapping)
class ProviderStatusMappingAdmin(admin.ModelAdmin):
    list_display = ('provider', 'provider_status_code', 'bink_status_code')
    list_filter = ('provider', 'bink_status_code')
    search_fields = ('provider_status_code', 'bink_status_code')


@admin.register(models.AuthTransaction)
class AuthTransactionAdmin(admin.ModelAdmin):
    list_display = ('payment_card_account', 'time', 'amount', 'mid', 'third_party_id',)
    search_fields = ('payment_card_account', 'mid', 'third_party_id',)


class PaymentCardUserAssociation(PaymentCardAccountEntry):
    """
    We are using a proxy model in admin for sole purpose of using an appropriate table name which is then listed
    in schemes and not ubiquity.  Using SchemeAccountEntry directly adds an entry in Ubiquity section called
    SchemeAccountEntry which would confuse users as it is not ubiquity specific and is not a way of entering
    scheme accounts ie it used to associate a scheme with a user.

    """
    class Meta:
        proxy = True


@admin.register(PaymentCardUserAssociation)
class PaymentCardUserAssociationAdmin(admin.ModelAdmin):
    list_display = ('payment_card_account', 'payment_account_link', 'user', 'card_pan_start', 'card_pan_end', 'card_is_deleted', 'card_created')

    def payment_account_link(self, obj):
        return format_html('<a href="/admin/payment_card/paymentcardaccount/{0}/change/">card id{0}</a>',
                           obj.payment_card_account.id)

    def card_pan_start(self, obj):
        return obj.payment_card_account.pan_start

    def card_pan_end(self, obj):
        return obj.payment_card_account.pan_end

    def card_is_deleted(self, obj):
        return obj.payment_card_account.is_deleted

    def card_created(self, obj):
        return obj.payment_card_account.created


admin.site.register(models.Issuer)
