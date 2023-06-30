# Generated by Django 2.2.14 on 2021-02-26 09:43

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0045_customuser_magic_link_verified"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="magic_lifetime",
            field=models.PositiveIntegerField(
                blank=True, default=60, null=True, validators=[django.core.validators.MinValueValidator(5)]
            ),
        ),
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="magic_link_url",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
