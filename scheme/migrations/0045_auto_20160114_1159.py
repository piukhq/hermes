# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0044_auto_20160114_1049'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='barcode_regex',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Regex to map card number to barcode'),
        ),
        migrations.AddField(
            model_name='scheme',
            name='card_number_regex',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Regex to map barcode to card number'),
        ),
    ]
