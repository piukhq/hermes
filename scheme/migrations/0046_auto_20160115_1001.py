# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0045_auto_20160114_1159'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='barcode_prefix',
            field=models.CharField(null=True, blank=True, help_text='Prefix to from card number -> barcode mapping', max_length=100),
        ),
        migrations.AddField(
            model_name='scheme',
            name='card_number_prefix',
            field=models.CharField(null=True, blank=True, help_text='Prefix to from barcode -> card number mapping', max_length=100),
        ),
    ]
