# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-28 09:55
from __future__ import unicode_literals

from django.db import migrations, models

import user.models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0021_data_bink_clientappbundle"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientapplication",
            name="secret",
            field=models.CharField(db_index=True, default=user.models._get_random_string, max_length=128, unique=True),
        ),
    ]
