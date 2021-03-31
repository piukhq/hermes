from django.contrib.postgres.fields import JSONField
from django.db import models
from .actions.vop_actions import Correction


class ScriptResult(models.Model):
    script_name = models.CharField(max_length=100, default="unknown")
    item_id = models.CharField(max_length=100, default="unknown")
    done = models.BooleanField(default=False)
    data = JSONField(default=dict, null=True, blank=True)
    results = JSONField(default=list, null=True, blank=True)
    correction = models.IntegerField(choices=Correction.CORRECTION_SCRIPTS,
                                     default=0, help_text='Correction Required', db_index=True)
    apply = models.IntegerField(choices=Correction.CORRECTION_SCRIPTS, default=0, help_text='Correction to Apply Now',
                                db_index=True)
