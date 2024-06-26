# Generated by Django 2.2.19 on 2021-04-21 14:14

from django.db import migrations

import user.forms
import user.models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0049_clientapplicationbundle_template"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientapplicationbundle",
            name="template",
            field=user.forms.MagicLinkTemplateFileField(
                blank=True, null=True, upload_to=user.models.magic_link_file_path
            ),
        ),
    ]
