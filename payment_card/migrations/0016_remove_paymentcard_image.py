# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-07-27 09:40
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0015_auto_20160715_1344"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="paymentcard",
            name="image",
        ),
    ]
