# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

from scheme.credentials import BARCODE


def set_scan_question(apps, schema_editor):
    """
    Set the scan_question to the manual_question if the manual_question type is a barcode
    """
    scheme_cls = apps.get_model("scheme", "Scheme")
    scheme_question_cls = apps.get_model("scheme", "SchemeCredentialQuestion")

    for scheme in scheme_cls.objects.all():
        if scheme.manual_question:
            scheme.manual_question.manual_question = True
            scheme.manual_question.save()

        if scheme.scan_question:
            scheme.scan_question.scan_question = True
            scheme.scan_question.save()


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0047_auto_20160118_1104'),
    ]

    operations = [
        migrations.RunPython(set_scan_question),
    ]
