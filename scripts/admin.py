from django.conf.urls import url
from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from .vop_scripts import find_deleted_vop_cards_with_activations
from .vop_actions import do_un_eroll, do_re_enroll, do_deactivate, do_mark_as_deactivated, do_transfer_activation

from .models import ScriptResult


def apply_correction(modeladmin, request, queryset):
    count = 0
    for entry in queryset:
        success = False
        if not entry.done:
            if entry.apply == ScriptResult.UN_ENROLL:
                success = do_un_eroll(entry)
            elif entry.apply == ScriptResult.DEACTIVATE:
                success = do_deactivate(entry)
            elif entry.apply == ScriptResult.RE_ENROLL:
                success = do_re_enroll(entry)
            elif entry.apply == ScriptResult.TRANSFER_ACTIVATION:
                success = do_transfer_activation(entry)
            elif entry.apply == ScriptResult.MARK_AS_DEACTIVATED:
                success = do_mark_as_deactivated(entry)
        if success:
            sequence = entry.data['sequence']
            sequence_pos = entry.data['sequence_pos'] + 1
            if sequence_pos >= len(sequence):
                entry.done = True
            else:
                entry.data['sequence_pos'] = sequence_pos
                entry.apply = sequence[sequence_pos]
            entry.save()


@admin.register(ScriptResult)
class ScriptResultAdmin(admin.ModelAdmin):
    list_display = ('script_name', 'item_id', 'done', 'apply', 'correction')
    list_filter = ('script_name', 'done', 'apply', 'correction',)
    readonly_fields = ('script_name', 'item_id', 'data', 'results', 'correction', 'apply', 'done')
    search_fields = ('script_name', 'done', 'data', 'results')
    list_per_page = 500
    actions = [apply_correction]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('run_script/<int:script_id>', self.admin_site.admin_view(self.run_script))
        ]
        return my_urls + urls

    def run_script(self, request, script_id):
        result = scripts_to_run(script_id)
        context = dict(
            self.admin_site.each_context(request),
            **result
        )
        return TemplateResponse(request, "admin/scripts/runscripttemplate.html", context)


def scripts_to_run(script_id):
    result = {
        'run_title': "No Script Found",
        'summary': "",
        'corrections': 0,
        'html_report': "",
    }
    if script_id == 1:
        result['run_title'] = "Deleted VOP Cards with remaining activations"
        result['summary'], result['corrections'], result['html_report'] = \
            find_deleted_vop_cards_with_activations(script_id, result['run_title'])
    return result
