from django import forms
from django.contrib import admin
from django.contrib.admin import StackedInline, SimpleListFilter
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _
from scheme.models import SchemeBundleAssociation
from ubiquity.models import ServiceConsent
from django.contrib import messages
from scheme.admin import check_active_scheme, CacheResetAdmin
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
    model = CustomUser.all_objects

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
    readonly_fields = ("delete_token", "magic_link_verified",)


class CustomUserConsent(CustomUser):

    class Meta:
        proxy = True
        verbose_name = 'Custom user service consent'
        verbose_name_plural = f"{verbose_name}s"


class HasServiceConsentFilter(SimpleListFilter):
    title = 'Has service consent'
    parameter_name = 'has_service_consent'

    def lookups(self, request, model_admin):
        return (
            ('True', _('True')),
            ('False', _('False')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(serviceconsent__isnull=False)
        if self.value() == 'False':
            return queryset.filter(serviceconsent__isnull=True)


@admin.register(CustomUserConsent)
class CustomUserServiceConsentAdmin(admin.ModelAdmin):
    list_per_page = 100

    def first_name(self, obj):
        return obj.profile.first_name

    def last_name(self, obj):
        return obj.profile.last_name

    def gender(self, obj):
        return obj.profile.gender

    def date_of_birth(self, obj):
        return obj.profile.date_of_birth

    def service_consent_timestamp(self, obj):
        try:
            return obj.serviceconsent.timestamp
        except obj.DoesNotExist:
            return None

    first_name.admin_order_field = 'profile__first_name'
    last_name.admin_order_field = 'profile__last_name'
    service_consent_timestamp.admin_order_field = 'serviceconsent__timestamp'

    form = CustomUserModelForm
    inlines = (ServiceConsentInline, UserDetailInline)
    ordering = ()
    fieldsets = ()
    add_fieldsets = ()
    list_display = ('email', 'uid', 'external_id', 'last_name', 'client', 'service_consent_timestamp',
                    'is_active', 'is_staff',)
    list_filter = ('is_active', 'is_staff', 'client', HasServiceConsentFilter,)
    filter_horizontal = ()
    search_fields = ('email', 'uid', 'external_id', 'profile__first_name', 'profile__last_name',
                     'serviceconsent__timestamp',)
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


class SchemeInline(admin.TabularInline):
    model = SchemeBundleAssociation
    raw_id_fields = ("scheme",)
    extra = 1
    verbose_name = 'Schemes'


@admin.register(ClientApplicationBundle)
class ClientApplicationBundleAdmin(CacheResetAdmin):
    list_display = ('bundle_id', 'client', 'external_name', 'magic_link_url', 'magic_lifetime')
    search_fields = ('bundle_id', 'client__name', 'client__organisation__name')
    filter_horizontal = ('scheme', 'issuer')
    list_filter = ('client__organisation__name', 'client__name', 'issuer', 'magic_link_url', 'scheme')
    inlines = [
        SchemeInline,
    ]
    current_bundle_status = {}

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        cleaned = formset.cleaned_data
        for clean_item in cleaned:
            scheme = clean_item.get('scheme')
            status = clean_item.get('status', SchemeBundleAssociation.INACTIVE)
            if status == SchemeBundleAssociation.ACTIVE:
                error, message = check_active_scheme(scheme)
                if error:
                    old_status = self.current_bundle_status.get(scheme.id, None)
                    if old_status is None or old_status == SchemeBundleAssociation.ACTIVE:
                        old_status = SchemeBundleAssociation.INACTIVE
                    messages.error(request,
                                   f"ERROR - scheme {scheme.name} status reverted"
                                   f" to {SchemeBundleAssociation.STATUSES[old_status][1]} because {message}")
                    SchemeBundleAssociation.objects.filter(scheme_id=scheme.id).update(status=old_status)

    def save_model(self, request, obj, form, change):
        current_bundles = SchemeBundleAssociation.objects.filter(bundle__bundle_id=obj.bundle_id)\
            .values('scheme_id', 'status')
        self.current_bundle_status = \
            {current_bundle['scheme_id']: current_bundle['status'] for current_bundle in current_bundles}
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        allowed_issuers = None
        bundle_id = None
        return_fields = ((None, {'fields': (('bundle_id', 'client', 'external_name'),
                                            ('magic_link_url', 'magic_lifetime'))}),)
        choice_description = "Schemes"

        if obj:
            allowed_issuers = [issuer.pk for issuer in obj.issuer.all()]
            bundle_id = obj.bundle_id

        if bundle_id:
            if bundle_id == 'com.bink.wallet':
                choice_description = "Available Schemes for the Bink app."
            elif obj:
                choice_description = "Available schemes. (Warning if used by Bink app existing users will need to" \
                                     " login to use this scheme)"
        else:
            choice_description = "No Schemes are Accessible with this bundle (Please add required schemes below)"

        SchemeInline.verbose_name_plural = choice_description
        if bundle_id != 'com.bink.wallet':
            if allowed_issuers:
                issuers_description = "<h3>Note: This feature only applies to Ubiquity</h3>"
                return_fields += (
                    ('All Issuers are currently permitted - click "show" to remove issuers from this bundle',
                     {
                         'classes': ('wide',),
                         'description': issuers_description,
                         'fields': ('issuer',),
                     }),
                )

            else:
                issuers_description = "<h3 style='color:red;'>Note: To activate this feature for Ubiquity make at" \
                                      " least one choice.  All issuers will be permitted until a choice is made</h3>"
                return_fields += (
                    ('For Ubiquity All Issuers are currently permitted - click "show" to remove '
                     'issuers from this bundle',
                     {
                         'classes': ('collapse',),
                         'description': issuers_description,
                         'fields': ('issuer',),
                     }),
                )

        return return_fields


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(ClientApplicationKit)
admin.site.register(Setting)
admin.site.register(MarketingCode)
