from django.contrib import admin
from django.utils.html import format_html

from payment_card.admin import titled_filter
from ubiquity.models import PaymentCardSchemeEntry, MembershipPlanDocument


@admin.register(PaymentCardSchemeEntry)
class PaymentCardSchemeEntryAdmin(admin.ModelAdmin):
    list_display = ('payment_card_account', 'scheme_account', 'active_link', 'payment_card_account_link',
                    'scheme_account_link', 'pay_status', 'is_pay_deleted', 'scheme_status', 'is_scheme_deleted',
                    'pay_created')
    search_fields = ('payment_card_account__pan_start', 'payment_card_account__pan_end', 'payment_card_account__token',
                     'scheme_account__scheme__name', 'payment_card_account__payment_card__name')

    list_filter = (('payment_card_account__payment_card__name', titled_filter('payment card')),
                   ('scheme_account__scheme', titled_filter('membership card')),
                   'active_link',
                   ('payment_card_account__issuer__name', titled_filter('payment card issuer')),
                   ('payment_card_account__is_deleted', titled_filter('payment card is deleted')),
                   ('scheme_account__is_deleted', titled_filter('membership card is deleted')),
                   ('payment_card_account__status', titled_filter('payment card status')),
                   ('scheme_account__status', titled_filter('membership card status')),
                   )
    raw_id_fields = ('payment_card_account', 'scheme_account',)

    def payment_card_account_link(self, obj):
        return format_html('<a href="/admin/payment_card/paymentcardaccount/{0}/change/">'
                           'card (id{0}) No. {1}...{2}</a>',
                           obj.payment_card_account.id, obj.payment_card_account.pan_start,
                           obj.payment_card_account.pan_end)

    def scheme_account_link(self, obj):
        return format_html('<a href="/admin/scheme/schemeaccount/{0}/change/">scheme id{0}</a>',
                           obj.scheme_account.id)

    def pay_status(self, obj):
        return obj.payment_card_account.status_name

    def scheme_status(self, obj):
        return obj.scheme_account.status_name

    def pay_created(self, obj):
        return obj.payment_card_account.created

    def is_scheme_deleted(self, obj):
        return obj.scheme_account.is_deleted

    def is_pay_deleted(self, obj):
        return obj.payment_card_account.is_deleted

    is_pay_deleted.boolean = True
    is_scheme_deleted.boolean = True


@admin.register(MembershipPlanDocument)
class MembershipPlanDocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'scheme', 'url', 'display', 'checkbox')
    search_fields = ('name', 'scheme__name', 'url', 'display')
    list_filter = ('scheme',)
    raw_id_fields = ('scheme',)
