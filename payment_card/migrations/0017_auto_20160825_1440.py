# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-08-25 14:40
from __future__ import unicode_literals

import datetime

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0016_remove_paymentcard_image"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="paymentcardaccountimagecriteria",
            name="payment_card",
        ),
        migrations.RemoveField(
            model_name="paymentcardaccountimagecriteria",
            name="payment_card_accounts",
        ),
        migrations.RemoveField(
            model_name="paymentcardaccountimagecriteria",
            name="payment_card_image",
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="end_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="payment_card",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="payment_card.PaymentCard"
            ),
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="payment_card_accounts",
            field=models.ManyToManyField(
                related_name="payment_card_accounts_set", to="payment_card.PaymentCardAccount"
            ),
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="start_date",
            field=models.DateTimeField(default=timezone.make_aware(datetime.datetime(1970, 1, 1, 0, 0))),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="status",
            field=models.IntegerField(choices=[(0, "draft"), (1, "published")], default=0),
        ),
        migrations.DeleteModel(
            name="PaymentCardAccountImageCriteria",
        ),
    ]
