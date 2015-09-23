# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0006_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeimage',
            name='call_to_action',
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
