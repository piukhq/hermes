from django.contrib import admin
from scheme.models import Scheme, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer, \
    SchemeCredentialQuestion


class SchemeImageInline(admin.StackedInline):
    model = SchemeImage
    extra = 0

class CredentialQuestionInline(admin.StackedInline):
    model = SchemeCredentialQuestion
    extra = 0

class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, CredentialQuestionInline)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "primary_question":
            try:
                pk = int(request.path.split('/')[-2])
                kwargs["queryset"] = SchemeCredentialQuestion.objects.filter(scheme_id=pk)
            except ValueError:
                kwargs["queryset"] = SchemeCredentialQuestion.objects.none()
        return super(SchemeAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountCredentialAnswerInline(admin.TabularInline):
    model = SchemeAccountCredentialAnswer
    extra = 0


class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountCredentialAnswerInline, )
    list_filter = ('status', )
    list_display = ('user', 'scheme', 'status')

admin.site.register(SchemeAccount, SchemeAccountAdmin)


admin.site.register(Category)

