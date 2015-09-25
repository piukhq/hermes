from django.contrib import admin
from scheme.models import Scheme, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer


class SchemeImageInline(admin.StackedInline):
    model = SchemeImage
    extra = 0


class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, )

admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountCredentialAnswerInline(admin.TabularInline):
    model = SchemeAccountCredentialAnswer
    extra = 0


class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountCredentialAnswerInline, )
    list_filter = ('status', )

admin.site.register(SchemeAccount, SchemeAccountAdmin)


admin.site.register(Category)
