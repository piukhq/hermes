# Generated by Django 1.9.2 on 2016-05-23 09:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0005_setting_scheme"),
    ]

    operations = [
        migrations.AlterField(
            model_name="setting",
            name="scheme",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="scheme.Scheme"
            ),
        ),
    ]
