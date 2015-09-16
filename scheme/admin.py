from django.contrib import admin
from scheme.models import Scheme, SchemeAccount, SchemeAccountSecurityQuestion, SchemeImage, Category


class SchemeImageInline(admin.StackedInline):
    model = SchemeImage
    extra = 0


class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, )

admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountSecurityQuestionInline(admin.TabularInline):
    model = SchemeAccountSecurityQuestion
    extra = 0

class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountSecurityQuestionInline, )
    list_filter = ('status', )

admin.site.register(SchemeAccount, SchemeAccountAdmin)


admin.site.register(Category)
