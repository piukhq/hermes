from django.contrib import admin

from .models import PeriodicRetry


@admin.register(PeriodicRetry)
class PeriodicRetryAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_group', 'function', 'status', 'retry_count', 'max_retry_attempts', 'next_retry_after',
                    'created_on',)
    readonly_fields = ('created_on', 'modified_on',)
    search_fields = ('id', 'status', 'task_group', 'function', 'module',)
