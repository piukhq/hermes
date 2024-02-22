# Generated by Django 1.9.2 on 2016-09-23 10:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0021_auto_20160916_1628"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcard",
            name="token_method",
            field=models.IntegerField(
                choices=[(0, "Use PSP token"), (1, "Generate length-24 token"), (2, "Generate length-25 token")],
                default=0,
            ),
        ),
    ]
