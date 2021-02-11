from common.admin import InputFilter
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.actions import delete_selected
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet, ModelForm
from django.utils.html import format_html
from redis import Redis

from history.utils import HistoryAdmin
from scheme.forms import ConsentForm, SchemeForm
from scheme.models import (Scheme, Exchange, SchemeAccount, SchemeImage, Category, SchemeAccountCredentialAnswer,
                           SchemeCredentialQuestion, SchemeAccountImage, Consent, UserConsent, SchemeBalanceDetails,
                           SchemeCredentialQuestionChoice, SchemeCredentialQuestionChoiceValue, Control, SchemeDetail,
                           ThirdPartyConsentLink, SchemeBundleAssociation, VoucherScheme, SchemeContent, SchemeFee)
from ubiquity.models import SchemeAccountEntry


r = Redis(connection_pool=settings.REDIS_WRITE_API_CACHE_POOL)


def delete_membership_plans_cache():
    # Delete all caches for m_plan key slug including all by id ones
    for key in r.scan_iter("m_plans:*"):
        r.delete(key)


def replaced_delete_selected(model_admin, request, queryset):
    if request.POST.get('post') == 'yes':
        ret = delete_selected(model_admin, request, queryset)
        delete_membership_plans_cache()
        return ret  # (v2.2) returns a overrideable template (delete_selected_confirmation_template) with context
    else:
        return delete_selected(model_admin, request, queryset)


replaced_delete_selected.short_description = "Delete Selected and reset Cache"


class CacheResetAdmin(admin.ModelAdmin):
    """ This model removes the default delete_selected action using get_actions.  This is the documented method for
    Django v2.2 and later. Not as described for earlier versions on many help sites.
    A bulk delete which resets the cache when the delete is confirmed is then added as a replacement action i.e.
    replaced_delete_selected.
    Since we still need the delete_selected logic we this function from our replaced_delete_selected function.
    However, the confirmation this function used by default has the delete_selected action hard coded.
    We therefore tell delete_selected function to use our form which has replaced_delete_selected hard coded instead.
    This is done by setting  delete_selected_confirmation_template = my_template.html

    Note the replaced_delete_selected(..) function is called once to render the confirmation form with the action
    which in turn causes a second call to replaced_delete_selected; this time with a POST of the confirmation form's
    parameters which may be used to reset the cache after a return call to delete_selected has completed the delete.

    delete_model and save_model are conventional overrides for equivalent single model change events
    """
    actions = [replaced_delete_selected]
    delete_selected_confirmation_template = "admin/common/bulk_del_selected_confirmation.html"

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def save_model(self, request, obj, form, change):
        resp = super().save_model(request, obj, form, change)
        delete_membership_plans_cache()
        return resp     # currently resp is None but in case it ever changes

    def delete_model(self, request, obj):
        resp = super().delete_model(request, obj)
        delete_membership_plans_cache()
        return resp    # currently resp is None but in case it ever changes


def check_active_scheme(scheme):
    message = 'You must have a manual question when a scheme is set to active'
    if not scheme.manual_question:
        return True, message
    message = ""
    for question in scheme.questions.all():
        if question.answer_type == 2:
            if not question.choice:
                message = "When the answer_type field value is 'choice' you must provide the choices"
        elif question.choice:
            message = "The choice field should be filled only when answer_type value is 'choice'"

    return message != "", message


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


class CredentialQuestionInline(admin.StackedInline):
    model = SchemeCredentialQuestion
    formset = CredentialQuestionFormset
    fields = (
        'scheme',
        'order',
        'type',
        'label',
        ('third_party_identifier', 'manual_question', 'scan_question', 'one_question_link'),
        'options',
        'validation',
        'description',
        'answer_type',
        'choice',
        ('add_field', 'auth_field', 'register_field', 'enrol_field'),
    )
    extra = 0


class SchemeContentInline(admin.StackedInline):
    model = SchemeContent
    extra = 0


class SchemeFeeInline(admin.StackedInline):
    model = SchemeFee
    extra = 0


class SchemeBalanceDetailsInline(admin.StackedInline):
    model = SchemeBalanceDetails
    extra = 0


class ControlInline(admin.TabularInline):
    model = Control
    extra = 0


class SchemeDetailsInline(admin.StackedInline):
    model = SchemeDetail
    extra = 0


@admin.register(Scheme)
class SchemeAdmin(CacheResetAdmin):

    inlines = (
        SchemeContentInline, SchemeFeeInline, SchemeDetailsInline, SchemeBalanceDetailsInline, ControlInline,
        CredentialQuestionInline,
    )
    exclude = []
    list_display = ('name', 'id', 'category', 'company',)

    form = SchemeForm
    search_fields = ['name']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields


@admin.register(SchemeImage)
class SchemeImageAdmin(CacheResetAdmin):
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


class CardNumberFilter(InputFilter):
    parameter_name = 'card_number'
    title = 'Card Number Containing:'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        card_number = Q(schemeaccountcredentialanswer__answer__icontains=term,
                        schemeaccountcredentialanswer__question__type='card_number')
        return queryset.filter(card_number)


class UserEmailFilter(InputFilter):
    parameter_name = 'user_email'
    title = 'User Email Containing'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        any_email = Q(schemeaccountentry__user__email__icontains=term)
        return queryset.filter(any_email)


class CredentialEmailFilter(InputFilter):
    parameter_name = 'credential_email'
    title = 'Credential Email Containing'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        any_email = Q(schemeaccountcredentialanswer__answer__icontains=term,
                      schemeaccountcredentialanswer__question__type='email')
        return queryset.filter(any_email)


class SchemeAccountEntryInline(admin.TabularInline):
    model = SchemeAccountEntry
    extra = 0
    readonly_fields = ('scheme_account', 'user', 'auth_status')

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SchemeAccount)
class SchemeAccountAdmin(HistoryAdmin):
    inlines = (SchemeAccountEntryInline, SchemeAccountCredentialAnswerInline,)
    list_filter = (CardNumberFilter, UserEmailFilter, CredentialEmailFilter, 'is_deleted', 'status', 'scheme',)
    list_display = ('scheme', 'user_email', 'status', 'is_deleted', 'created')
    list_per_page = 25

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('scheme', 'link_date')
        return self.readonly_fields

    def credential_email(self, obj):
        credential_emails = SchemeAccountCredentialAnswer.objects.filter(scheme_account=obj.id,
                                                                         question__type__exact='email')
        user_list = [x.answer for x in credential_emails]
        return format_html('</br>'.join(user_list))

    def user_email(self, obj):
        user_list = [format_html('<a href="/admin/user/customuser/{}/change/">{}</a>',
                                 assoc.user.id, assoc.user.email if assoc.user.email else assoc.user.uid)
                     for assoc in SchemeAccountEntry.objects.filter(scheme_account=obj.id)]
        return format_html('</br>'.join(user_list))

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if request.GET.get('card_number', None) is not None:
            self.list_per_page = 10
            list_display = list_display[:4] + ('card_number',) + list_display[-1:]
        if request.GET.get('credential_email', None) is not None:
            self.list_per_page = 10
            list_display = list_display[:2] + ('credential_email',) + list_display[2:]
        else:
            self.list_per_page = 25
        return list_display

    credential_email.allow_tags = True
    user_email.allow_tags = True


class SchemeUserAssociation(SchemeAccountEntry):
    """
    We are using a proxy model in admin for sole purpose of using an appropriate table name which is then listed
    in schemes and not ubiquity.  Using SchemeAccountEntry directly adds an entry in Ubiquity section called
    SchemeAccountEntry which would confuse users as it is not ubiquity specific and is not a way of entering
    scheme accounts ie it used to associate a scheme with a user.

    """

    class Meta:
        proxy = True
        verbose_name = "Scheme Account to User Association"
        verbose_name_plural = "".join([verbose_name, 's'])


class AssocCardNumberFilter(InputFilter):
    parameter_name = 'scheme_account_card_number'
    title = 'Card Number Containing:'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        card_number = Q(scheme_account__schemeaccountcredentialanswer__answer__icontains=term,
                        scheme_account__schemeaccountcredentialanswer__question__type='card_number')
        return queryset.filter(card_number)


class AssocUserEmailFilter(InputFilter):
    parameter_name = 'user_email'
    title = 'User Email Containing'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        any_email = Q(user__email__icontains=term)
        return queryset.filter(any_email)


@admin.register(SchemeUserAssociation)
class SchemeUserAssociationAdmin(HistoryAdmin):
    list_display = ('scheme_account', 'user', 'scheme_account_link', 'user_link', 'scheme_status', 'scheme_is_deleted',
                    'scheme_created')
    search_fields = ['scheme_account__scheme__name', 'user__email', 'user__external_id', ]
    list_filter = (AssocCardNumberFilter, AssocUserEmailFilter, 'scheme_account__is_deleted', 'scheme_account__status',
                   'scheme_account__scheme',)
    raw_id_fields = ('scheme_account', 'user',)

    def scheme_account_link(self, obj):
        return format_html('<a href="/admin/scheme/schemeaccount/{0}/change/">scheme id{0}</a>',
                           obj.scheme_account.id)

    def user_link(self, obj):
        user_name = obj.user.external_id
        if not user_name:
            user_name = obj.user.get_username()
        if not user_name:
            user_name = obj.user.email
        return format_html('<a href="/admin/user/customuser/{}/change/">{}</a>',
                           obj.user.id, user_name)

    def scheme_account_card_number(self, obj):
        return obj.scheme_account.card_number

    def scheme_status(self, obj):
        return obj.scheme_account.status_name

    def scheme_created(self, obj):
        return obj.scheme_account.created

    def scheme_is_deleted(self, obj):
        return obj.scheme_account.is_deleted

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if request.GET.get('scheme_account_card_number', None) is not None:
            self.list_per_page = 15
            list_display = list_display + ('scheme_account_card_number',)
        else:
            self.list_per_page = 100
        return list_display

    scheme_is_deleted.boolean = True


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


@admin.register(ThirdPartyConsentLink)
class ThirdPartyConsentLinkAdmin(CacheResetAdmin):
    form = ModelForm
    fields = (
        'consent_label',
        'client_app',
        'scheme',
        'consent',
        ('add_field', 'auth_field', 'register_field', 'enrol_field'),
    )
    list_display = ('consent_label', 'client_app', 'scheme', 'consent')
    list_filter = ('client_app', 'scheme', 'consent')
    search_fields = ['scheme__name', 'consent__slug', 'client_app__name']


admin.site.register(Category)


@admin.register(SchemeBundleAssociation)
class SchemeBundleAssociationAdmin(CacheResetAdmin):
    list_display = ('bundle', 'scheme', 'status', 'test_scheme')
    search_fields = ('bundle_id', 'scheme__name')
    raw_id_fields = ("scheme",)
    list_filter = ('bundle', 'scheme', 'status', 'test_scheme')

    def save_form(self, request, form, change):
        ret = super().save_form(request, form, change)
        clean_item = form.cleaned_data
        scheme = clean_item.get('scheme')
        status = clean_item.get('status', SchemeBundleAssociation.INACTIVE)
        old_status = form.initial.get('status', None)
        if status == SchemeBundleAssociation.ACTIVE:
            error, message = check_active_scheme(scheme)
            if error:
                if old_status is None or old_status == SchemeBundleAssociation.ACTIVE:
                    old_status = SchemeBundleAssociation.INACTIVE
                messages.error(request,
                               f"ERROR - scheme {scheme.name} status reverted"
                               f" to {SchemeBundleAssociation.STATUSES[old_status][1]} because {message}")
                ret.status = old_status
        return ret


TEMPLATING_HELP_TEXT = """
<p>Use two curly braces to substitute values.</p>
<p>For example: <pre>\"{{earn_target_remaining}} left to go!\"</pre></p>
"""


@admin.register(VoucherScheme)
class VoucherSchemeAdmin(admin.ModelAdmin):
    list_display = ("scheme", "earn_type", "burn_type", "expiry_months")
    list_filter = ("scheme", "earn_type", "burn_type")
    fieldsets = (
        (None, {"fields": ("scheme", "barcode_type", "subtext", "expiry_months")}),
        ("Earn", {
            "fields": (
                "earn_currency",
                "earn_prefix",
                "earn_suffix",
                "earn_type",
                "earn_target_value",
            )
        }),
        ("Burn", {
            "fields": (
                "burn_currency",
                "burn_prefix",
                "burn_suffix",
                "burn_type",
                "burn_value",
            )
        }),
        ("Headlines", {
            "description": f'<div class="help">{TEMPLATING_HELP_TEXT}</div>',
            "fields": (
                "headline_inprogress",
                "headline_expired",
                "headline_redeemed",
                "headline_issued",
            )
        }),
        ("Body Text", {
            "fields": (
                "body_text_inprogress",
                "body_text_expired",
                "body_text_redeemed",
                "body_text_issued",
            )
        }),
    )
