# Generated by Django 2.2.14 on 2020-08-12 09:51

from django.db import migrations


def make_staff_superusers(apps, schema_editor):
    CustomUser = apps.get_model("user", "CustomUser")
    CustomUser.all_objects.filter(is_staff=True, is_superuser=False).update(is_superuser=True)


def revert_make_staff_superusers(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0043_auto_20200804_0919"),
    ]

    operations = [
        migrations.RunPython(make_staff_superusers, revert_make_staff_superusers),
    ]
