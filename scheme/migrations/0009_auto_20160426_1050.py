# Generated by Django 1.9.2 on 2016-04-26 10:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0008_auto_20160413_0849"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccountimagecriteria",
            name="description",
            field=models.CharField(default="Desc", max_length=300),
            preserve_default=False,
        ),
    ]
