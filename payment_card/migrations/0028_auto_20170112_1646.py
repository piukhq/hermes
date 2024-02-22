# Generated by Django 1.9.2 on 2017-01-12 16:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0027_auto_20161124_1138"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderStatusMapping",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_status_code", models.CharField(max_length=24)),
                ("bink_status_code", models.IntegerField(choices=[(0, "pending"), (1, "active")])),
                (
                    "provider",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="payment_card.PaymentCard"),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="paymentcardaccountimage",
            name="payment_card_accounts",
            field=models.ManyToManyField(
                blank=True, related_name="payment_card_accounts_set", to="payment_card.PaymentCardAccount"
            ),
        ),
    ]
