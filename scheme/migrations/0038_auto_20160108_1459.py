# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def set_scheme_account_answer(apps, schema_editor):
    scheme_account_cls = apps.get_model("scheme", "SchemeAccount")
    question_cls = apps.get_model("scheme", "SchemeCredentialQuestion")

    for scheme_account in scheme_account_cls.objects.all():
        for answer in scheme_account.schemeaccountcredentialanswer_set.all():
            try:
                answer.question = question_cls.objects.get(type=answer.type, scheme_id=scheme_account.scheme.id)
                answer.save()
            except question_cls.DoesNotExist:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0037_auto_20160108_1458'),
    ]

    operations = [
        migrations.RunPython(set_scheme_account_answer),
    ]
