from django.contrib.auth.admin import UserAdmin
from user.models import CustomUser, UserDetail, Referral
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


class CustomUserDetail(UserAdmin):
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
