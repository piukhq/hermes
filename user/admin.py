from django import forms
from django.contrib.admin import StackedInline
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin

from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount
from user.models import CustomUser, UserDetail, Referral, UserSetting, Setting


class UserDetailInline(admin.StackedInline):
    model = UserDetail
    extra = 0


class UserSchemeAccountsInline(StackedInline):
    model = SchemeAccount
    extra = 0


class UserPaymentCardAccountInline(StackedInline):
    model = PaymentCardAccount
    extra = 0


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
    inlines = (UserDetailInline, UserSchemeAccountsInline, UserPaymentCardAccountInline)
    ordering = ()
    fieldsets = ()
    add_fieldsets = ()
    list_display = ('email', 'uid', 'first_name', 'last_name', 'gender', 'date_of_birth', 'is_active', 'is_staff',)
    list_filter = ('is_staff',)
    filter_horizontal = ()
    search_fields = ('email', 'uid', 'profile__first_name', 'profile__last_name',)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'recipient', 'date',)


@admin.register(UserSetting)
class UserSettingAdmin(admin.ModelAdmin):
    search_fields = ('user__email', 'setting__slug', 'value')


admin.site.register(Setting)
