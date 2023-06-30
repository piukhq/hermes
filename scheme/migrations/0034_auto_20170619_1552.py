# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-19 14:52
from __future__ import unicode_literals

import colorful.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0033_auto_20170601_0958"),
    ]

    operations = [
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop),
        migrations.AlterField(
            model_name="scheme",
            name="android_app_id",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Android app ID"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="barcode_prefix",
            field=models.CharField(
                blank=True, default="", help_text="Prefix to from card number -> barcode mapping", max_length=100
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="barcode_regex",
            field=models.CharField(
                blank=True, default="", help_text="Regex to map card number to barcode", max_length=100
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="card_number_prefix",
            field=models.CharField(
                blank=True, default="", help_text="Prefix to from barcode -> card number mapping", max_length=100
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="card_number_regex",
            field=models.CharField(
                blank=True, default="", help_text="Regex to map barcode to card number", max_length=100
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="colour",
            field=colorful.fields.RGBColorField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="company_url",
            field=models.URLField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="forgotten_password_url",
            field=models.URLField(blank=True, default="", max_length=500),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="identifier",
            field=models.CharField(blank=True, default="", help_text="Regex identifier for barcode", max_length=30),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="ios_scheme",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="iOS scheme"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="itunes_url",
            field=models.URLField(blank=True, default="", verbose_name="iTunes URL"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="join_url",
            field=models.URLField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="link_account_text",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="play_store_url",
            field=models.URLField(blank=True, default="", verbose_name="Play store URL"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="scheme",
            name="point_name",
            field=models.CharField(
                blank=True,
                default="points",
                help_text="This field must have a length that, when added to the value of the above field, is less than or equal to 10.",
                max_length=10,
            ),
        ),
        migrations.RunSQL(migrations.RunSQL.noop, reverse_sql="SET CONSTRAINTS ALL IMMEDIATE"),
    ]
