# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-06-23 09:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0012_auto_20160620_1243"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="order",
            field=models.IntegerField(),
        ),
        migrations.AlterUniqueTogether(
            name="paymentcardaccount",
            unique_together=set([("fingerprint", "expiry_month", "expiry_year")]),
        ),
    ]
