# Generated by Django 2.2.26 on 2022-01-13 16:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0100_auto_20211213_1126"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheme",
            name="tier",
            field=models.IntegerField(choices=[(1, "PLL"), (2, "Store"), (3, "Engage"), (4, "Coming Soon")]),
        ),
    ]
