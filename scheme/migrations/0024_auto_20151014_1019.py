# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0023_auto_20151014_1008'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='has_points',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='has_transactions',
            field=models.BooleanField(default=False),
        ),
    ]
