# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0022_scheme_barcode_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='point_conversion_rate',
            field=models.DecimalField(null=True, max_digits=20, blank=True, decimal_places=6),
        ),
    ]
