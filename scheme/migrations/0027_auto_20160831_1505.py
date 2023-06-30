# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-08-31 15:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0026_auto_20160825_1259"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccountimage",
            name="size_code",
            field=models.CharField(blank=True, default="", max_length=30),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="schemeaccountimage",
            name="strap_line",
            field=models.CharField(blank=True, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="schemeaccountimage",
            name="url",
            field=models.URLField(blank=True, default=""),
            preserve_default=False,
        ),
    ]
