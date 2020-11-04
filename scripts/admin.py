from django.conf.urls import url
from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from .scripts import find_deleted_vop_cards_with_activations

from .models import ScriptResult


@admin.register(ScriptResult)
class ScriptResultAdmin(admin.ModelAdmin):
    list_display = ('script_name', 'item_id', 'done', 'apply', 'correction')

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







