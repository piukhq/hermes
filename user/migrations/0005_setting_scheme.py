# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-05-23 09:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0017_auto_20160523_0923'),
        ('user', '0004_setting_usersetting'),
    ]

    operations = [
        migrations.AddField(
            model_name='setting',
            name='scheme',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme'),
        ),
    ]
