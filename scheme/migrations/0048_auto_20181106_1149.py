# Generated by Django 1.11.1 on 2018-11-06 11:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0047_auto_20180927_1135"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheme",
            name="status",
            field=models.IntegerField(choices=[(0, "Active"), (1, "Suspended"), (2, "Inactive")], default=0),
        ),
    ]
