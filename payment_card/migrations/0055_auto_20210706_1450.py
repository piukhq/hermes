# Generated by Django 2.2.21 on 2021-07-06 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0054_paymentcardaccount_agent_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentcardaccount",
            name="card_nickname",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="paymentcardaccount",
            name="issuer_name",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
