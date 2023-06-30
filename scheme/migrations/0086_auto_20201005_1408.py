# Generated by Django 2.2.14 on 2020-10-05 13:08

import logging

import django.contrib.postgres.fields.jsonb
from django.db import migrations

logger = logging.getLogger(__name__)


def convert_empty_tx_dicts_to_list(apps, schema_editor):
    SchemeAccount = apps.get_model("scheme", "SchemeAccount")
    SchemeAccount.objects.filter(transactions={}).update(transactions=[])


def revert_empty_tx_dicts_to_list(apps, schema_editor):
    SchemeAccount = apps.get_model("scheme", "SchemeAccount")
    SchemeAccount.objects.filter(transactions=[]).update(transactions={})


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0085_auto_20201015_1202"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccount",
            name="transactions",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list, null=True),
        ),
        migrations.RunPython(convert_empty_tx_dicts_to_list, revert_empty_tx_dicts_to_list),
    ]
