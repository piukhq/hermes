# Generated by Django 2.2.14 on 2020-10-01 13:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0082_voucherscheme_earn_target_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucherscheme",
            name="body_text_cancelled",
            field=models.TextField(blank=True, default="", verbose_name="Cancelled"),
        ),
        migrations.AddField(
            model_name="voucherscheme",
            name="headline_cancelled",
            field=models.CharField(default="", max_length=250, verbose_name="Cancelled"),
        ),
    ]
