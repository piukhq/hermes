# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-10-16 10:10
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0036_auto_20180629_1453"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="paymentcardaccount",
            name="user",
        ),
        migrations.AddField(
            model_name="paymentcardaccount",
            name="consents",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=[]),
        ),
    ]
