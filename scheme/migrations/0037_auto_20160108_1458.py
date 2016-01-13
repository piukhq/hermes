# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0036_auto_20151204_1616'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='schemeaccount',
            options={'ordering': ['order', '-created']},
        ),
        migrations.AddField(
            model_name='schemeaccountcredentialanswer',
            name='question',
            field=models.ForeignKey(null=True, to='scheme.SchemeCredentialQuestion'),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='barcode_type',
            field=models.IntegerField(null=True, choices=[(0, 'CODE128 (B or C)'), (1, 'QrCode'), (2, 'AztecCode'), (3, 'Pdf417'), (4, 'EAN (13)'), (5, 'DataMatrix'), (6, 'ITF (Interleaved 2 of 5)'), (7, 'Code 39')], blank=True),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='scheme',
            field=models.ForeignKey(to='scheme.Scheme', on_delete=django.db.models.deletion.PROTECT, related_name='questions'),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='image_type_code',
            field=models.IntegerField(choices=[(0, 'hero'), (1, 'banner'), (2, 'offers'), (3, 'icon'), (4, 'asset'), (5, 'reference')]),
        ),
    ]
