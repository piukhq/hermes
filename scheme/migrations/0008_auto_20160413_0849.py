# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-04-13 08:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0007_remove_schemeaccountimagecriteria_payment_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccountimagecriteria",
            name="end_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
