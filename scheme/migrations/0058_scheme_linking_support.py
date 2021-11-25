# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-03-13 09:52
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheme", "0057_auto_20190307_1647"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheme",
            name="linking_support",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=50),
                blank=True,
                default=[],
                help_text="journeys supported by the scheme in the ubiquity endpoints, ie: ADD, REGISTRATION, ENROL",
                size=None,
            ),
        ),
    ]
