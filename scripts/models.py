from django.db import models
from django.db.models import JSONField

from .actions.schemeaccount_actions import SchemeAccountCorrection
from .actions.vop_actions import Correction

CHOICES = Correction.CORRECTION_SCRIPTS + SchemeAccountCorrection.CORRECTION_SCRIPTS


class ScriptResult(models.Model):
    script_name = models.CharField(max_length=100, default="unknown")
    item_id = models.CharField(max_length=100, default="unknown")
    done = models.BooleanField(default=False)
    data = JSONField(default=dict, null=True, blank=True)
    results = JSONField(default=list, null=True, blank=True)
    correction = models.IntegerField(choices=CHOICES, default=0, help_text="Correction Required", db_index=True)
    apply = models.IntegerField(choices=CHOICES, default=0, help_text="Correction to Apply Now", db_index=True)
