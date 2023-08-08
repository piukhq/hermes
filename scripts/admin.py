from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.urls import path

from .actions.corrections import Correction
from .models import ScriptResult
from .scripts import SCRIPT_CLASSES, SCRIPT_TITLES
from .tasks.async_corrections import background_corrections

# See scripts.py on how to add a new script find records function


def apply_correction(_, request, queryset):
    count = len(queryset)
    success_count = 0
    failed_count = 0
    done_count = 0

    if not user_can_run_script(request):
        messages.add_message(request, messages.WARNING, "Could not execute the script: Access Denied")
    else:
        for entry in queryset:
            if not entry.done:
                title = Correction.TITLES[entry.apply]
                success = Correction.do(entry)
                if success:
                    success_count += 1
                    sequence = entry.data["sequence"]
                    sequence_pos = entry.data["sequence_pos"] + 1
                    entry.results.append(f"{title}: success")
                    if sequence_pos >= len(sequence):
                        entry.done = True
                        entry.apply = Correction.NO_CORRECTION
                        done_count += 1

                    else:
                        entry.data["sequence_pos"] = sequence_pos
                        entry.apply = sequence[sequence_pos]
                else:
                    failed_count += 1
                    entry.results.append(f"{title}: failed")
                entry.save()
        messages.add_message(
            request,
            messages.INFO,
            f"Process {count} corrections - {success_count} successful,"
            f" {failed_count} failed, {done_count} completed",
        )


def apply_correction_in_background(_, request, queryset):
    count = len(queryset)

    if not user_can_run_script(request):
        messages.add_message(request, messages.WARNING, "Could not execute the script: Access Denied")
    else:
        background_corrections.delay(queryset)
        messages.add_message(
            request, messages.INFO, f"Processing {count} corrections in background - search results to see progress"
        )


def user_can_run_script(request):
    return request.user.has_perm("scripts.add_scriptresult")


@admin.register(ScriptResult)
class ScriptResultAdmin(admin.ModelAdmin):
    list_display = ("script_name", "item_id", "script_run_uid", "done", "apply", "correction", "results")
    list_filter = (
        "script_name",
        "done",
        "apply",
        "correction",
    )
    readonly_fields = ("script_run_uid", "script_name", "item_id", "data", "results", "correction", "apply", "done")
    search_fields = ("script_run_uid", "item_id", "script_name", "done", "data", "results")
    list_per_page = 500
    actions = [apply_correction, apply_correction_in_background]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [path("run_script/<int:script_id>", self.admin_site.admin_view(self.run_script))]
        return my_urls + urls

    def run_script(self, request, script_id):
        result = scripts_to_run(script_id)
        context = dict(self.admin_site.each_context(request), **result)
        return TemplateResponse(request, "admin/scripts/runscripttemplate.html", context)


def scripts_to_run(script_id):
    result = {
        "run_title": "No Script Found",
        "summary": "",
        "corrections": 0,
        "html_report": "",
    }

    for data_script, function in SCRIPT_CLASSES.items():
        if script_id == data_script.value:
            result["run_title"] = SCRIPT_TITLES[script_id]
            script_class = function(script_id, result["run_title"])
            result["summary"], result["corrections"], result["html_report"] = script_class.run()
            break
    return result
