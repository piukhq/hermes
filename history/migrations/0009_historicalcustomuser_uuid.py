# Generated by Django 4.0.4 on 2022-05-27 08:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("history", "0008_alter_historicalcustomuser_body_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalcustomuser",
            name="uuid",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]