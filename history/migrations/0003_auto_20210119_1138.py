# Generated by Django 2.2.14 on 2021-01-19 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("history", "0002_auto_20210118_1151"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalschemeaccount",
            name="journey",
            field=models.CharField(
                choices=[("n/a", "n/a"), ("add", "add"), ("register", "register"), ("enrol", "enrol")],
                default="n/a",
                max_length=8,
            ),
        ),
    ]
