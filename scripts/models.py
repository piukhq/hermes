from django.contrib.postgres.fields import JSONField
from django.db import models


class ScriptResult(models.Model):
    NO_CORRECTION = 0
    MARK_AS_DEACTIVATED = 1
    TRANSFER_ACTIVATION = 2
    DEACTIVATE_UN_ENROLLED = 3
    RE_ENROLL = 4
    DEACTIVATE = 5
    UN_ENROLL = 6

    CORRECTION_SCRIPTS = (
        (NO_CORRECTION, 'No correction available'),
        (MARK_AS_DEACTIVATED, 'Mark as deactivated as same token is also active'),
        (TRANSFER_ACTIVATION, 'Transfer activation to card with same token'),
        (DEACTIVATE_UN_ENROLLED, 'Re-enrol, Deactivate, Un-enroll'),
        (RE_ENROLL, 'Re-enroll'),
        (DEACTIVATE, 'Deactivate'),
        (UN_ENROLL, 'Un-enroll'),
    )

    script_name = models.CharField(max_length=100, default="unknown")
    item_id = models.CharField(max_length=100, default="unknown")
    done = models.BooleanField(default=False)
    data = JSONField(default=dict, null=True, blank=True)
    results = JSONField(default=list, null=True, blank=True)
    correction = models.IntegerField(choices=CORRECTION_SCRIPTS, default=0, help_text='Correction Required',
                                     db_index=True)
    apply = models.IntegerField(choices=CORRECTION_SCRIPTS, default=0, help_text='Correction to Apply Now',
                                db_index=True)
