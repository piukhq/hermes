# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-23 16:04
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0012_clientapplication"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="clientapplication",
            name="secret",
        ),
    ]
