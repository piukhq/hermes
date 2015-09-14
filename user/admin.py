from django.contrib import admin
from user.models import CustomUser, UserDetail

admin.site.register(CustomUser)
admin.site.register(UserDetail)
