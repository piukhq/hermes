# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0021_auto_20151014_1004'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='barcode_type',
            field=models.IntegerField(choices=[(0, 'CODE128 (B or C)'), (1, 'QrCode'), (2, 'AztecCode'), (3, 'Pdf417'),
                                               (4, 'EAN (13)'), (5, 'DataMatrix'), (6, 'ITF (Interleaved 2 of 5)')],
                                      null=True, blank=True),
        ),
    ]
