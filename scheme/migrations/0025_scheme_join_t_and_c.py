# Generated by Django 1.9.2 on 2016-08-19 11:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0024_auto_20160817_1512"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheme",
            name="join_t_and_c",
            field=models.TextField(blank=True, verbose_name="Join terms & conditions"),
        ),
    ]
