# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-08-07 09:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0030_organisation_terms_and_conditions"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="salt",
            field=models.CharField(default="", max_length=8),
            preserve_default=False,
        ),
    ]
