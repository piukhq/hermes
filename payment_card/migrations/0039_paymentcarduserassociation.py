# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-01-08 15:02
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ubiquity", "0002_auto_20181205_1640"),
        ("payment_card", "0038_auto_20181107_1158"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentCardUserAssociation",
            fields=[],
            options={
                "verbose_name": "Payment Card Account to User Association",
                "verbose_name_plural": "Payment Card Account to User Associations",
                "proxy": True,
                "indexes": [],
            },
            bases=("ubiquity.paymentcardaccountentry",),
        ),
    ]
