# Generated by Django 4.0.7 on 2022-11-01 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0056_customuser_last_accessed"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="is_trusted",
            field=models.BooleanField(default=False),
        ),
    ]