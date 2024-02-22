# Generated by Django 1.9.2 on 2017-03-24 12:26

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0015_auto_20170324_0952"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientApplicationBundle",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bundle_id", models.CharField(max_length=200)),
            ],
        ),
        migrations.AddField(
            model_name="clientapplication",
            name="organisation",
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to="user.Organisation"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="client_application",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="user.ClientApplication"),
        ),
    ]
