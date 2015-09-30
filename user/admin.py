from django.contrib import admin
from user.models import CustomUser, UserDetail


class UserDetailInline(admin.StackedInline):
    model = UserDetail
    extra = 0


class CustomUserDetail(admin.ModelAdmin):
    inlines = (UserDetailInline, )


admin.site.register(CustomUser, CustomUserDetail)

