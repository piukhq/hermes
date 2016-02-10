# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

from scheme.credentials import BARCODE


def set_scan_question(apps, schema_editor):
    """
    Set the scan_question to the manual_question if the manual_question type is a barcode
    """
    scheme_cls = apps.get_model("scheme", "Scheme")

    for scheme in scheme_cls.objects.all():
        if scheme.manual_question and scheme.manual_question.type == BARCODE:
            scheme.scan_question = scheme.manual_question
            scheme.save()


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0043_auto_20160114_1048'),
    ]

    operations = [
        migrations.RunPython(set_scan_question),
    ]
