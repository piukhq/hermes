# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0042_auto_20160113_1636'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='scan_question',
            field=models.ForeignKey(null=True, to='scheme.SchemeCredentialQuestion', related_name='scan_question', blank=True),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='manual_question',
            field=models.ForeignKey(null=True, to='scheme.SchemeCredentialQuestion', related_name='manual_question', blank=True),
        ),
    ]
