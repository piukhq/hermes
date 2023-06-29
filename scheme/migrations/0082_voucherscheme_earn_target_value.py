# Generated by Django 2.2.14 on 2020-08-10 16:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0081_schemeaccount_formatted_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucherscheme",
            name="earn_target_value",
            field=models.FloatField(
                blank=True,
                help_text="Enter a value in this field if the merchant scheme does not return an earn.target_value for the voucher",
                null=True,
                verbose_name="Earn Target Value",
            ),
        ),
    ]
