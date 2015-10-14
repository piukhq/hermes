# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0019_scheme_has_points'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='barcode_type',
            field=models.CharField(choices=[('CODE128', 'CODE128 (B or C)'), ('EAN', 'EAN (13)'), ('UPC', 'UPC-A'), ('CODE39', 'CODE39'), ('ITF', 'ITF (Interleaved 2 of 5)'), ('ITF14', 'ITF14'), ('PHARMADCODE', 'Pharmacode')], blank=True, max_length=20, null=True),
        ),
    ]
