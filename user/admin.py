from django import forms
from django.contrib import admin
from django.contrib.admin import StackedInline
from django.contrib.auth.admin import UserAdmin

from ubiquity.models import ServiceConsent
from user.models import (ClientApplication, ClientApplicationBundle, ClientApplicationKit, CustomUser, MarketingCode,
                         Organisation, Referral, Setting, UserDetail, UserSetting)


class UserDetailInline(admin.StackedInline):
    model = UserDetail
    extra = 0


class UserSchemeAccountsInline(StackedInline):
    model = CustomUser.scheme_account_set.through
    exclude = ('membership_card_data',)
    extra = 0


class ServiceConsentInline(admin.StackedInline):
    model = ServiceConsent
    readonly_fields = ('latitude', 'longitude', 'timestamp')

    extra = 0


class UserPaymentCardAccountInline(StackedInline):
    model = CustomUser.payment_card_account_set.through
    exclude = ('payment_card_data',)
    extra = 0
    # readonly_fields = ('token', 'psp_token', )


class CustomUserModelForm(forms.ModelForm):
    jwt_token = forms.CharField(required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        if user:
            if not kwargs.get('initial'):
                kwargs['initial'] = {}
            kwargs['initial'].update({'jwt_token': user.create_token()})
        super(CustomUserModelForm, self).__init__(*args, **kwargs)

    class Meta:
        model = CustomUser
        fields = '__all__'


@admin.register(CustomUser)
class CustomUserDetail(UserAdmin):

    def first_name(self, obj):
        return obj.profile.first_name

    def last_name(self, obj):
        return obj.profile.last_name

    def gender(self, obj):
        return obj.profile.gender

    def date_of_birth(self, obj):
        return obj.profile.date_of_birth

    first_name.admin_order_field = 'profile__first_name'
    last_name.admin_order_field = 'profile__last_name'

    form = CustomUserModelForm
    inlines = (ServiceConsentInline, UserDetailInline)
    ordering = ()
    fieldsets = ()
    add_fieldsets = ()
    list_display = ('email', 'uid', 'external_id', 'last_name', 'date_of_birth', 'is_active', 'is_staff',)
    list_filter = ('is_staff',)
    filter_horizontal = ()
    search_fields = ('email', 'uid', 'external_id', 'profile__first_name', 'profile__last_name',)
    exclude = ('salt',)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'recipient', 'date',)


@admin.register(UserSetting)
class UserSettingAdmin(admin.ModelAdmin):
    search_fields = ('user__email', 'setting__slug', 'value')


@admin.register(ClientApplication)
class ClientApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'organisation', 'client_id')
    search_fields = ('name', 'organisation__name', 'client_id')


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    filter_horizontal = ('schemes', 'issuers')


admin.site.register([ClientApplicationBundle, ClientApplicationKit])
admin.site.register(Setting)
admin.site.register(MarketingCode)
