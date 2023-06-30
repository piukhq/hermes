# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-29 08:52
from __future__ import unicode_literals

from django.db import migrations


def apply_bink_app_core_kit(apps, schema_editor):
    ClientApplication = apps.get_model("user", "ClientApplication")
    ClientApplicationKit = apps.get_model("user", "ClientApplicationKit")
    bink_app = ClientApplication.objects.get(name="Bink")
    ClientApplicationKit.objects.create(client_id=bink_app.client_id, kit_name="core")


def unapply_bink_app_core_kit(apps, schema_editor):
    ClientApplicationKit = apps.get_model("user", "ClientApplicationKit")
    ClientApplicationKit.objects.filter(client__name="Bink", kit_name="core").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0025_clientapplicationkit"),
    ]

    operations = [
        migrations.RunPython(apply_bink_app_core_kit, unapply_bink_app_core_kit),
    ]
