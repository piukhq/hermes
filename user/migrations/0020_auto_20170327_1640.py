# Generated by Django 1.9.2 on 2017-03-27 16:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0019_data_existing_users_bink_clientapp"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="customuser",
            unique_together=set([("client", "email")]),
        ),
    ]
