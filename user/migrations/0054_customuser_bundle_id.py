# Generated by Django 2.2.25 on 2022-02-08 13:42

from django.db import migrations, models



def populate_bundle_id(apps, schema_editor):
    # some users in dev database had no bundle_id
    # hence the check for cab
    CustomUser = apps.get_model("user", "CustomUser")
    for user in CustomUser.all_objects.filter(is_active=True).all():        
        cab = user.client.clientapplicationbundle_set.first()
        if cab:
            user.bundle_id = cab.bundle_id
            user.save()
    

def reverse_bundle_id(apps, schema_editor):
    # once field is removed nothing more to do here
    pass


class Migration(migrations.Migration):


    dependencies = [
        ("user", "0053_clientapplicationbundle_email_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="bundle_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(populate_bundle_id, reverse_bundle_id),
    ]
