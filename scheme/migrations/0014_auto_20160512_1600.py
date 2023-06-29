# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-05-12 16:00
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0013_auto_20160511_1501"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="scheme",
            name="Android app ID",
        ),
        migrations.RemoveField(
            model_name="scheme",
            name="Play store URL",
        ),
        migrations.RemoveField(
            model_name="scheme",
            name="iOS scheme",
        ),
        migrations.RemoveField(
            model_name="scheme",
            name="iTunes URL",
        ),
        migrations.AddField(
            model_name="scheme",
            name="android_app_id",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Android app ID"),
        ),
        migrations.AddField(
            model_name="scheme",
            name="ios_scheme",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="iOS scheme"),
        ),
        migrations.AddField(
            model_name="scheme",
            name="itunes_url",
            field=models.URLField(blank=True, null=True, verbose_name="iTunes URL"),
        ),
        migrations.AddField(
            model_name="scheme",
            name="play_store_url",
            field=models.URLField(blank=True, null=True, verbose_name="Play store URL"),
        ),
    ]
