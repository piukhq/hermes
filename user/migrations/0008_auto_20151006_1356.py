# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0007_auto_20150922_1236'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetail',
            name='currency',
            field=models.CharField(max_length=3, blank=True, null=True, default='GBP'),
        ),
    ]
