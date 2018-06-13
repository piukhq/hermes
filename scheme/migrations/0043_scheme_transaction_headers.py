# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-06-12 16:07
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0042_consent_userconsent'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='transaction_headers',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=40), default=['Date', 'Reference', 'Points'], size=None),
        ),
    ]
