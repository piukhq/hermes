# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0004_auto_20150915_1342'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='is_valid',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='membership_number',
            field=models.CharField(null=True, max_length=50, blank=True),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='order',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='updated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
