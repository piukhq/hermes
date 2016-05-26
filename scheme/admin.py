from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, ModelForm

from scheme.models import (Scheme, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer,
                           SchemeCredentialQuestion, SchemeAccountImageCriteria, SchemeAccountImage)


class SchemeImageInline(admin.StackedInline):
    model = SchemeImage
    extra = 0


class CredentialQuestionFormset(BaseInlineFormSet):
    def clean(self):
        super().clean()
        manual_questions = [form.cleaned_data['manual_question'] for form in self.forms]
        if manual_questions.count(True) > 1:
            raise ValidationError("You may only select one manual question")

        scan_questions = [form.cleaned_data['scan_question'] for form in self.forms]
        if scan_questions.count(True) > 1:
            raise ValidationError("You may only select one scan question")

        if self.instance.is_active and not any(manual_questions):
            raise ValidationError("You must have a manual question when a scheme is set to active")


class CredentialQuestionInline(admin.TabularInline):
    model = SchemeCredentialQuestion
    formset = CredentialQuestionFormset
    extra = 0


class SchemeForm(ModelForm):
    class Meta:
        model = Scheme
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_point_name(self):
        point_name = self.cleaned_data['point_name']
        points_value_length = self.cleaned_data['max_points_value_length']

        if len(point_name) + points_value_length + 1 > Scheme.MAX_POINTS_VALUE_LENGTH:
            raise ValidationError('The length of the point name added to the maximum points value length must not '
                                  'exceed {}'.format(Scheme.MAX_POINTS_VALUE_LENGTH - 1))

        return point_name


class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeImageInline, CredentialQuestionInline)
    exclude = []
    list_display = ('name', 'id', 'category', 'is_active', 'company')
    list_filter = ('is_active', )
    form = SchemeForm

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not request.user.is_superuser and object_id:
            self.exclude.append('slug')
        return super().change_view(request, object_id, form_url='', extra_context=None)

admin.site.register(Scheme, SchemeAdmin)


class SchemeAccountCredentialAnswerInline(admin.TabularInline):
    model = SchemeAccountCredentialAnswer
    extra = 0

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == "question":
            try:
                pk = int(request.path.split('/')[-3])
                scheme_account = SchemeAccount.all_objects.get(id=pk)
                kwargs["queryset"] = SchemeCredentialQuestion.objects.filter(scheme_id=scheme_account.scheme.id)
            except ValueError:
                kwargs["queryset"] = SchemeCredentialQuestion.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountCredentialAnswerInline, )
    list_filter = ('is_deleted', 'status', 'scheme')
    list_display = ('user', 'scheme', 'status', 'is_deleted')


class SchemeAccountImageCriteriaAdmin(admin.ModelAdmin):
    model = SchemeAccountImageCriteria
    filter_horizontal = ('scheme_accounts',)


admin.site.register(SchemeAccount, SchemeAccountAdmin)
admin.site.register(Category)
admin.site.register(SchemeAccountImageCriteria, SchemeAccountImageCriteriaAdmin)
admin.site.register(SchemeAccountImage)
