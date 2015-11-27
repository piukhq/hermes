from django.contrib.auth.admin import UserAdmin
from user.models import CustomUser, UserDetail
from django.contrib import admin


class UserDetailInline(admin.StackedInline):
    model = UserDetail
    extra = 0


class CustomUserDetail(UserAdmin):
    inlines = (UserDetailInline, )
    ordering = ()
    fieldsets = ()
    add_fieldsets = ()
    list_display = ('email', 'uid')
    list_filter = ('is_staff', )
    filter_horizontal = ()
    search_fields = ('email', 'uid')


admin.site.register(CustomUser, CustomUserDetail)
