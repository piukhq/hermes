# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-05-11 15:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0012_auto_20160511_1448'),
    ]

    operations = [
        migrations.RenameField(
            model_name='scheme',
            old_name='playstore_url',
            new_name='Play store URL',
        ),
        migrations.RenameField(
            model_name='scheme',
            old_name='itunes_url',
            new_name='iTunes URL',
        ),
        migrations.RemoveField(
            model_name='scheme',
            name='android_app_id',
        ),
        migrations.RemoveField(
            model_name='scheme',
            name='ios_scheme',
        ),
        migrations.AddField(
            model_name='scheme',
            name='Android app ID',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='scheme',
            name='iOS scheme',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
