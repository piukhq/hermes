# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0008_auto_20151006_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='facebook',
            field=models.CharField(max_length=120, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='twitter',
            field=models.CharField(max_length=120, blank=True, null=True),
        ),
    ]
