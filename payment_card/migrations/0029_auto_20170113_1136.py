# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-01-13 11:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0028_auto_20170112_1646"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "pending"),
                    (1, "active"),
                    (2, "duplicate card"),
                    (3, "not provider card"),
                    (4, "invalid card details"),
                    (5, "provider server down"),
                    (6, "unknown"),
                ],
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="providerstatusmapping",
            name="bink_status_code",
            field=models.IntegerField(
                choices=[
                    (0, "pending"),
                    (1, "active"),
                    (2, "duplicate card"),
                    (3, "not provider card"),
                    (4, "invalid card details"),
                    (5, "provider server down"),
                    (6, "unknown"),
                ]
            ),
        ),
    ]
