from celery.result import GroupResult
from django.db import models

from scripts.actions.corrections import Correction
from scripts.enums import ShirleyStatuses

CHOICES = Correction.CORRECTION_SCRIPTS


class ScriptResult(models.Model):
    script_name = models.CharField(max_length=100, default="unknown")
    item_id = models.CharField(max_length=100, default="unknown")
    done = models.BooleanField(default=False)
    data = models.JSONField(default=dict, null=True, blank=True)
    results = models.JSONField(default=list, null=True, blank=True)
    correction = models.IntegerField(choices=CHOICES, default=0, help_text="Correction Required", db_index=True)
    apply = models.IntegerField(choices=CHOICES, default=0, help_text="Correction to Apply Now", db_index=True)
    script_run_uid = models.UUIDField(blank=True, null=True)


class ShirleyYouCantBeSerious(models.Model):
    _STATUSES = [
        (ShirleyStatuses.READY, "Ready"),
        (ShirleyStatuses.IN_PROGRESS, "In Progress"),
        (ShirleyStatuses.DONE, "Done"),
    ]

    correction = models.IntegerField(
        choices=Correction.SHIRLEY_CORRECTION_SCRIPTS, help_text="Correction Required", db_index=True
    )
    batch_size = models.IntegerField(default=1)
    input_file = models.FileField()
    success_file = models.FileField(blank=True, null=True)
    failed_file = models.FileField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=_STATUSES, default=ShirleyStatuses.READY, db_index=True)
    status_description = models.TextField(blank=True, null=True)
    celery_group_id = models.CharField(max_length=36, blank=True, null=True)
    created_tasks_n = models.IntegerField(default=0)

    @property
    def celery_group_result(self) -> GroupResult | None:
        if self.status == ShirleyStatuses.IN_PROGRESS and self.celery_group_id:
            return GroupResult.restore(self.celery_group_id)

        return None

    def __str__(self) -> str:
        return f"{self.pk}, {self.correction}, {self.status}"
