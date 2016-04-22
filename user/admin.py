from django import forms
from django.contrib.auth.admin import UserAdmin
from user.models import CustomUser, UserDetail, Referral, UserSetting, Setting
from django.contrib import admin


def first_name(obj):
    user = UserDetail.objects.get(user=obj)
    return user.first_name


def last_name(obj):
    user = UserDetail.objects.get(user=obj)
    return user.last_name


def gender(obj):
    user = UserDetail.objects.get(user=obj)
    return user.gender


def date_of_birth(obj):
    user = UserDetail.objects.get(user=obj)
    return user.date_of_birth


class UserDetailInline(admin.StackedInline):
    model = UserDetail
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


class CustomUserDetail(UserAdmin):

    form = CustomUserModelForm
    inlines = (UserDetailInline, )
    ordering = ()
    fieldsets = ()
    add_fieldsets = ()
    list_display = ('email', 'uid', first_name, last_name, gender, date_of_birth, 'is_active', 'is_staff')
    list_filter = ('is_staff', )
    filter_horizontal = ()
    search_fields = ('email', 'uid')


admin.site.register(CustomUser, CustomUserDetail)


class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'recipient', 'date')


admin.site.register(Referral, ReferralAdmin)

admin.site.register(Setting)
admin.site.register(UserSetting)
