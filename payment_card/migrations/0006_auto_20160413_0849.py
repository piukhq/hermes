# Generated by Django 1.9.2 on 2016-04-13 08:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0005_paymentaccountimagecriteria"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentaccountimagecriteria",
            name="end_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
