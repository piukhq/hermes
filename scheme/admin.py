from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, ModelForm
from django.utils.html import format_html
from scheme.forms import ConsentForm
from scheme.models import (Scheme, Exchange, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer,
                           SchemeCredentialQuestion, SchemeAccountImage, Consent, UserConsent, SchemeBalanceDetails,
                           SchemeCredentialQuestionChoice, SchemeCredentialQuestionChoiceValue, Control, SchemeDetail)

from ubiquity.models import SchemeAccountEntry

import re

slug_regex = re.compile(r'^[a-z0-9\-]+$')


class CredentialQuestionFormset(BaseInlineFormSet):

    def _collect_form_data(self):
        manual_questions = [form.cleaned_data['manual_question'] for form in self.forms]
        choice = [form.cleaned_data['choice'] for form in self.forms]
        answer_type = [form.cleaned_data['answer_type'] for form in self.forms]
        return manual_questions, choice, answer_type

    def clean(self):
        super().clean()
        manual_questions, choice, answer_type = self._collect_form_data()

        if manual_questions.count(True) > 1:
            raise ValidationError("You may only select one manual question")

        scan_questions = [form.cleaned_data['scan_question'] for form in self.forms]
        if scan_questions.count(True) > 1:
            raise ValidationError("You may only select one scan question")

        if self.instance.is_active:
            if not any(manual_questions):
                raise ValidationError("You must have a manual question when a scheme is set to active")

            for pos, answer in enumerate(answer_type):
                if answer == 2:
                    if not choice[pos]:
                        raise ValidationError(
                            "When the answer_type field value is 'choice' you must provide the choices")
                elif choice[pos]:
                    raise ValidationError("The choice field should be filled only when answer_type value is 'choice'")


class CredentialQuestionInline(admin.StackedInline):
    model = SchemeCredentialQuestion
    formset = CredentialQuestionFormset
    extra = 0


class SchemeBalanceDetailsInline(admin.StackedInline):
    model = SchemeBalanceDetails
    extra = 0


class ControlInline(admin.TabularInline):
    model = Control
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

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if slug_regex.match(slug):
            return slug
        else:
            raise ValidationError('Slug can only contain lowercase letters, hyphens and numbers')


class SchemeDetailsInline(admin.StackedInline):
    model = SchemeDetail
    extra = 0


@admin.register(Scheme)
class SchemeAdmin(admin.ModelAdmin):
    inlines = (SchemeDetailsInline, SchemeBalanceDetailsInline, CredentialQuestionInline, ControlInline)
    exclude = []
    list_display = ('name', 'id', 'category', 'is_active', 'company',)
    list_filter = ('status',)
    form = SchemeForm
    search_fields = ['name']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields


@admin.register(SchemeImage)
class SchemeImageAdmin(admin.ModelAdmin):
    list_display = ('scheme', 'description', 'image_type_code_name', 'status', 'start_date', 'end_date', 'created',)
    list_filter = ('scheme', 'image_type_code', 'status', 'created')
    search_fields = ('scheme__name', 'description')
    raw_id_fields = ('scheme',)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


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


@admin.register(SchemeAccount)
class SchemeAccountAdmin(admin.ModelAdmin):
    inlines = (SchemeAccountCredentialAnswerInline,)
    list_filter = ('is_deleted', 'status', 'scheme',)
    list_display = ('scheme', 'user_email', 'status', 'is_deleted', 'created',)
    search_fields = ['scheme__name', 'schemeaccountentry__user__email']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('scheme', 'link_date')
        return self.readonly_fields

    def user_email(self, obj):
        user_list = [format_html('<a href="/admin/user/customuser/{}/change/">{}</a>',
                                 assoc.user.id, assoc.user.email if assoc.user.email else assoc.user.uid)
                     for assoc in SchemeAccountEntry.objects.filter(scheme_account=obj.id)]
        return '</br>'.join(user_list)

    user_email.allow_tags = True


@admin.register(SchemeAccountEntry)
class SchemeAccountEntryAdmin(admin.ModelAdmin):
    list_display = ('scheme_account', 'user', 'status')
    search_fields = ['scheme_account__scheme__name', 'user__email']

    def status(self, obj):
        return obj.scheme_account.status_name


@admin.register(SchemeAccountImage)
class SchemeAccountImageAdmin(admin.ModelAdmin):
    list_display = ('scheme', 'description', 'image_type_code_name', 'status', 'start_date', 'end_date', 'created',)
    list_filter = ('scheme', 'image_type_code', 'status', 'created')
    search_fields = ('scheme__name', 'description')
    raw_id_fields = ('scheme_accounts',)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    search_fields = ["host_scheme__name", "donor_scheme__name"]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super(ExchangeAdmin, self).get_search_results(request, queryset, search_term)
        try:
            if search_term.startswith("host:"):
                queryset |= self.model.objects.filter(host_scheme__name__contains=search_term.replace("host:", ""))
            elif search_term.startswith("donor:"):
                queryset |= self.model.objects.filter(donor_scheme__name__contains=search_term.replace("donor:", ""))

            return queryset, use_distinct
        except Exception:
            return queryset, use_distinct


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ('id', 'slug', 'scheme_account', 'status', 'short_text', 'value', 'created_on')
    search_fields = ('scheme_account', 'user', 'slug', 'journey', 'metadata__text', 'value')
    readonly_fields = ('metadata', 'value', 'scheme_account', 'slug', 'created_on', 'user', 'scheme', 'status')


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    form = ConsentForm
    list_display = ('id', 'check_box', 'short_text', 'scheme', 'is_enabled', 'required', 'order',
                    'journey', 'created_on', 'modified_on')
    search_fields = ('scheme__slug', 'text')
    list_filter = ('scheme__slug', 'journey', 'check_box', 'order', 'required', 'is_enabled')

    def get_queryset(self, request):
        return Consent.all_objects.all()

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug', 'check_box')
        return self.readonly_fields


class SchemeCredentialQuestionChoiceValueInline(admin.TabularInline):
    model = SchemeCredentialQuestionChoiceValue
    formset = BaseInlineFormSet
    extra = 0


@admin.register(SchemeCredentialQuestionChoice)
class SchemeCredentialQuestionChoiceAdmin(admin.ModelAdmin):
    inlines = (SchemeCredentialQuestionChoiceValueInline,)
    exclude = []
    list_display = ('scheme_question', 'scheme',)
    list_filter = ('scheme_question', 'scheme',)
    raw_id_fields = ('scheme',)
    form = ModelForm
    search_fields = ['scheme']


admin.site.register(Category)
