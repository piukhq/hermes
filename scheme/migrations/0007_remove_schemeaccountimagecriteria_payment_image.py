# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-04-12 11:10
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scheme", "0006_auto_20160411_1356"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="schemeaccountimagecriteria",
            name="payment_image",
        ),
    ]
