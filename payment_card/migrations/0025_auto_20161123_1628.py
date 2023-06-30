# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-11-23 16:28
from __future__ import unicode_literals

from django.db import migrations
from django.db.models.functions import Length


def update_pan_end(apps, schema_editor):
    accounts = (
        apps.get_model("payment_card", "PaymentCardAccount")
        .all_objects.annotate(text_len=Length("pan_end"))
        .filter(text_len__gt=4)
    )
    for account in accounts:
        original_pan_end = list(str(account.pan_end))
        original_pan_end[0] = "•"
        new_pan_end = "".join(original_pan_end)
        account.pan_end = new_pan_end
        account.save()


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0024_auto_20161026_1626"),
    ]

    operations = [migrations.RunPython(update_pan_end)]
