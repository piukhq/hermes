# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0003_auto_20150915_1236'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='point_conversion_rate',
            field=models.DecimalField(decimal_places=6, max_digits=20),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='tier',
            field=models.IntegerField(choices=[(1, 'Tier 1'), (2, 'Tier 2')]),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
