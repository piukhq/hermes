from django.contrib import admin
from django.contrib import messages
from django.template.response import TemplateResponse
from django.urls import path

from .models import ScriptResult
from .scripts import SCRIPT_TITLES, SCRIPT_FUNCTIONS, DataScripts
from .vop_actions import do_un_eroll, do_re_enroll, do_deactivate, do_mark_as_deactivated, do_transfer_activation


# See scripts.py on hoe to add a new script find records function


def apply_correction(modeladmin, request, queryset):
    count = 0
    success_count = 0
    failed_count = 0
    done_count = 0
    correction_titles = dict(ScriptResult.CORRECTION_SCRIPTS)
    for entry in queryset:
        count += 1
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
                success_count += 1
                sequence = entry.data['sequence']
                sequence_pos = entry.data['sequence_pos'] + 1
                entry.results.append(f"{correction_titles[entry.apply]}: success")
                if sequence_pos >= len(sequence):
                    entry.done = True
                    entry.apply = ScriptResult.NO_CORRECTION
                    done_count += 1

                else:
                    entry.data['sequence_pos'] = sequence_pos
                    entry.apply = sequence[sequence_pos]
            else:
                failed_count += 1
                entry.results.append(f"{correction_titles[entry.apply]}: failed")
            entry.save()
    messages.add_message(request, messages.INFO, f'Process {count} corrections - {success_count} successful,'
                                                 f' {failed_count} failed, {done_count} completed')


@admin.register(ScriptResult)
class ScriptResultAdmin(admin.ModelAdmin):
    list_display = ('script_name', 'item_id', 'done', 'apply', 'correction', 'results')
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

    for data_script, function in SCRIPT_FUNCTIONS.items():
        if script_id == data_script.value:
            result['run_title'] = SCRIPT_TITLES[DataScripts.DEL_VOP_WITH_ACT]
            result['summary'], result['corrections'], result['html_report'] = \
                function(script_id, result['run_title'])
            break
    return result
