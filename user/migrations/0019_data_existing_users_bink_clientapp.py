# Generated by Django 1.9.2 on 2017-03-27 09:50

from django.db import migrations

BINK_APP_ID = "MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd"


def set_bink_client_on_users(apps, schema_editor):
    CustomUser = apps.get_model("user", "CustomUser")
    ClientApplication = apps.get_model("user", "ClientApplication")
    get_users = lambda: CustomUser.objects.filter(client_id__isnull=True)
    get_users().update(client_id=BINK_APP_ID)
    assert get_users().count() == 0


def unset_bink_client_on_users(apps, schema_editor):
    CustomUser = apps.get_model("user", "CustomUser")
    ClientApplication = apps.get_model("user", "ClientApplication")
    get_users = lambda: CustomUser.objects.filter(client_id=BINK_APP_ID)
    get_users().update(client_id=None)
    assert get_users().count() == 0


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0018_customuser_client"),
    ]

    operations = [
        migrations.RunPython(set_bink_client_on_users, unset_bink_client_on_users),
    ]
