# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-11-24 11:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0026_auto_20161124_1136"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="pan_end",
            field=models.CharField(max_length=4),
        ),
    ]
