# Generated by Django 4.0.3 on 2022-03-08 16:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("history", "0007_auto_20220201_1726"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalcustomuser",
            name="body",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="historicalpaymentcardaccount",
            name="body",
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name="historicalschemeaccount",
            name="body",
            field=models.JSONField(),
        ),
    ]
