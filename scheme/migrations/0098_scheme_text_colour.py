# Generated by Django 2.2.24 on 2021-11-15 12:28

import colorful.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0097_auto_20211022_1227"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheme",
            name="text_colour",
            field=colorful.fields.RGBColorField(blank=True, default="#000000"),
        ),
    ]
