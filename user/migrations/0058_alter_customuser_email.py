# Generated by Django 4.0.7 on 2023-03-08 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0057_clientapplicationbundle_is_trusted"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=255, verbose_name="email address"),
            preserve_default=False,
        ),
    ]
