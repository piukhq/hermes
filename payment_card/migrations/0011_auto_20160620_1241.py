# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-06-20 12:41
from __future__ import unicode_literals

from django.db import migrations


def generate_dummy_fingerprints(apps, schema_editor):
    accounts = apps.get_model("payment_card", "PaymentCardAccount").objects.all()
    for account in accounts:
        if not account.fingerprint:
            account.fingerprint = "dummy-fingerprint-{}".format(account.id)
            account.save()


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0010_paymentcardaccount_fingerprint"),
    ]

    operations = [migrations.RunPython(generate_dummy_fingerprints)]
