# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-17 15:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0001_squashed_0009_paymentcardaccount_is_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='country',
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='currency_code',
            field=models.CharField(max_length=3),
        ),
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='token',
            field=models.CharField(max_length=255),
        ),
    ]
