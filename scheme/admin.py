from django.contrib import admin
from scheme.models import Scheme, SchemeAccount, SchemeAccountSecurityQuestion, SchemeImage


class SchemeImageInline(admin.TabularInline):
    model = SchemeImage


class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, )

admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountSecurityQuestionInline(admin.TabularInline):
    model = SchemeAccountSecurityQuestion


class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountSecurityQuestionInline, )
    list_filter = ('status', )

admin.site.register(SchemeAccount, SchemeAccountAdmin)
