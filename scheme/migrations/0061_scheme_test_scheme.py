# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-07-31 12:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0060_auto_20190627_1122'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='test_scheme',
            field=models.BooleanField(default=False),
        ),
    ]
