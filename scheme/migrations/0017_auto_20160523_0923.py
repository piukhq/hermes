# Generated by Django 1.9.2 on 2016-05-23 09:23

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0016_auto_20160513_1448"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheme",
            name="point_name",
            field=models.CharField(
                blank=True,
                default="points",
                help_text="This field must have a length that, when added to the value of the above field, is less than or equal to 10.",
                max_length=10,
                null=True,
            ),
        ),
    ]
