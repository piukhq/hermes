# Generated by Django 2.2.6 on 2019-10-28 09:42

from django.db import migrations


def create_service_client_app(apps, schema_editor):
    Organisation = apps.get_model("user", "Organisation")
    ClientApplication = apps.get_model("user", "ClientApplication")
    ClientApplicationBundle = apps.get_model("user", "ClientApplicationBundle")

    bink_org = Organisation.objects.get_or_create(name="Loyalty Angels")[0]

    daedalus_client = ClientApplication.objects.create(organisation=bink_org, name="Daedalus")
    ClientApplicationBundle.objects.create(client=daedalus_client, bundle_id="com.bink.daedalus")


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0038_auto_20191014_1121"),
    ]

    operations = [
        migrations.RunPython(create_service_client_app),
    ]
