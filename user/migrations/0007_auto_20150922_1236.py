# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0006_auto_20150914_1414'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetail',
            name='notifications',
            field=models.IntegerField(blank=True, choices=[(0, False), (1, True)], null=True),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='pass_code',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
