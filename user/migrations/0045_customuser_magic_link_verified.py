# Generated by Django 2.2.14 on 2021-02-25 10:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0044_auto_20200812_1051'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='magic_link_verified',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]