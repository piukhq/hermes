# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-09-26 09:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0034_auto_20180925_1505'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='external_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=255),
        ),
    ]
