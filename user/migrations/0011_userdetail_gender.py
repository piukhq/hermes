# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0010_auto_20151013_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetail',
            name='gender',
            field=models.CharField(choices=[('female', 'Female'), ('male', 'Male'), ('other', 'Other')], null=True, blank=True, max_length=6),
        ),
    ]
