# Generated by Django 1.11.7 on 2019-07-31 12:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0036_auto_20190627_1122"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_tester",
            field=models.BooleanField(default=False),
        ),
    ]
