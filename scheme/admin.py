from django.contrib import admin
from scheme.models import Scheme, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer, \
    SchemeCredentialQuestion


class SchemeImageInline(admin.StackedInline):
    model = SchemeImage
    extra = 0


class CredentialQuestionInline(admin.TabularInline):
    model = SchemeCredentialQuestion
    extra = 0


class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, CredentialQuestionInline)
    list_display = ('name', 'id', 'category', 'is_active', 'company')  # 'manual_question', 'scan_question'
    list_filter = ('is_active', )


admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountCredentialAnswerInline(admin.TabularInline):
    model = SchemeAccountCredentialAnswer
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "question":
            try:
                pk = int(request.path.split('/')[-2])
                scheme_account = SchemeAccount.objects.get(id=pk)
                kwargs["queryset"] = SchemeCredentialQuestion.objects.filter(scheme_id=scheme_account.scheme.id)
            except ValueError:
                kwargs["queryset"] = SchemeCredentialQuestion.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountCredentialAnswerInline, )
    list_filter = ('is_deleted', 'status', 'scheme')
    list_display = ('user', 'scheme', 'status', 'is_deleted')

admin.site.register(SchemeAccount, SchemeAccountAdmin)
admin.site.register(Category)
