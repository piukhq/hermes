from celery.result import GroupResult
from django.db import models

from scripts.corrections import Correction
from scripts.enums import FileScriptStatuses

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


class FileScript(models.Model):
    _FILE_UPLOAD_LOC = "file_script_files/"
    _CORRECTIONS_NAME_MAP = dict(Correction.FILE_CORRECTION_SCRIPTS)
    _STATUSES = [
        (FileScriptStatuses.READY, "Ready"),
        (FileScriptStatuses.IN_PROGRESS, "In Progress"),
        (FileScriptStatuses.DONE, "Done"),
    ]

    correction = models.IntegerField(
        choices=Correction.FILE_CORRECTION_SCRIPTS, help_text="Correction Required", db_index=True
    )
    batch_size = models.IntegerField(default=1)
    input_file = models.FileField(upload_to=_FILE_UPLOAD_LOC)
    success_file = models.FileField(upload_to=_FILE_UPLOAD_LOC, blank=True, null=True)
    failed_file = models.FileField(upload_to=_FILE_UPLOAD_LOC, blank=True, null=True)
    status = models.CharField(max_length=12, choices=_STATUSES, default=FileScriptStatuses.READY, db_index=True)
    status_description = models.TextField(blank=True, null=True)
    celery_group_id = models.CharField(max_length=36, blank=True, null=True)
    created_tasks_n = models.IntegerField(default=0)

    @property
    def celery_group_result(self) -> GroupResult | None:
        if self.status == FileScriptStatuses.IN_PROGRESS and self.celery_group_id:
            return GroupResult.restore(self.celery_group_id)

        return None

    def __str__(self) -> str:
        correction_name = self._CORRECTIONS_NAME_MAP.get(self.correction, "Unknown")
        return f"{self.pk}, {correction_name}, {self.status}"
