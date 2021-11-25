# Generated by Django 2.2.11 on 2020-03-13 10:49

from django.db import migrations, models

import payment_card.models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0042_auto_20191015_1455"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentaudit",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "PURCHASE_PENDING"),
                    (1, "PURCHASE_FAILED"),
                    (2, "AUTHORISED"),
                    (3, "SUCCESSFUL"),
                    (4, "VOID_REQUIRED"),
                    (5, "VOID_SUCCESSFUL"),
                ],
                default=payment_card.models.PaymentStatus(0),
            ),
        ),
        migrations.AlterField(
            model_name="paymentaudit",
            name="transaction_token",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
