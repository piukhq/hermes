# Generated by Django 1.11.1 on 2018-11-07 11:23

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0049_auto_20181107_1123"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="scheme",
            name="is_active",
        ),
    ]
