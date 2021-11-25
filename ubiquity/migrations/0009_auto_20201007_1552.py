# Generated by Django 2.2.14 on 2020-10-07 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ubiquity", "0008_auto_20200804_1448"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vopactivation",
            name="status",
            field=models.IntegerField(
                choices=[(1, "activating"), (2, "deactivating"), (3, "activated"), (4, "deactivated")],
                db_index=True,
                default=1,
                help_text="Activation Status",
            ),
        ),
    ]
