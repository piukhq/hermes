# Generated by Django 1.11.1 on 2018-06-29 13:18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0034_auto_20180129_1405"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthTransaction",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("time", models.DateTimeField()),
                ("amount", models.IntegerField()),
                ("mid", models.CharField(max_length=100)),
                ("third_party_id", models.CharField(max_length=100)),
                ("auth_code", models.CharField(max_length=100)),
                ("currency_code", models.CharField(default="GBP", max_length=3)),
                (
                    "payment_card_account",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to="payment_card.PaymentCardAccount"
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="paymentcard",
            name="system",
            field=models.CharField(
                choices=[("visa", "Visa"), ("mastercard", "Master Card"), ("amex", "American Express")], max_length=40
            ),
        ),
    ]
