# Generated by Django 2.2.11 on 2020-08-04 08:19
# Added User Groups Read and Read/Write

from django.db import migrations


def add_read_only_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    new_group = Group.objects.create(name="Read Only")
    permissions = Permission.objects.filter(codename__startswith='view')
    entry_data = [{"group_id": new_group.id, "permission_id": p.pk} for p in permissions]
    ThroughModel = new_group.permissions.through
    all_entries = [ThroughModel(**entry) for entry in entry_data]
    ThroughModel.objects.bulk_create(all_entries)


def add_read_write_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    new_group = Group.objects.create(name="Read/Write Only")
    permissions = Permission.objects.all()
    entry_data = [{"group_id": new_group.id, "permission_id": p.pk} for p in permissions]
    ThroughModel = new_group.permissions.through
    all_entries = [ThroughModel(**entry) for entry in entry_data]
    ThroughModel.objects.bulk_create(all_entries)


def revert_migration_read_only(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(
        name=u'Read Only',
    ).delete()


def revert_migration(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(
        name=u'Read/Write Only',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0042_auto_20200610_0933'),
    ]

    operations = [
        migrations.RunPython(add_read_only_group, revert_migration_read_only),
        migrations.RunPython(add_read_write_group, revert_migration),
    ]

