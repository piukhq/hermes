# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0020_auto_20151014_0933'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheme',
            name='barcode_type',
        ),
        migrations.AlterField(
            model_name='scheme',
            name='point_conversion_rate',
            field=models.DecimalField(decimal_places=6, null=True, max_digits=20),
        ),
    ]
