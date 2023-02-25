# Generated by Django 4.0.10 on 2023-02-25 02:50

import django.db.models.deletion
from django.db import migrations, models

import periodic_corrections.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("payment_card", "0058_delete_payment_card_different_expiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="PeriodicRetain",
            fields=[
                (
                    "payment_card_account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="payment_card.paymentcardaccount",
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        choices=[(0, "STOPPED"), (1, "RETRYING"), (2, "SUCCESSFUL")],
                        default=periodic_corrections.models.RetryStatus["RETRYING"],
                    ),
                ),
                ("message_key", models.CharField(blank=True, max_length=80, null=True)),
                ("succeeded", models.BooleanField(default=False)),
                ("retry_count", models.IntegerField(blank=True, default=0, null=True)),
                ("data", models.JSONField(blank=True, default=dict, null=True)),
                ("results", models.JSONField(blank=True, default=list, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
