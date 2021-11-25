# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-09-16 16:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0019_auto_20160913_1248"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcard",
            name="token_method",
            field=models.IntegerField(choices=[(0, "Use PSP token"), (1, "Generate length-24 token")], default=0),
        ),
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="psp_token",
            field=models.CharField(max_length=255, verbose_name="PSP Token"),
        ),
    ]
