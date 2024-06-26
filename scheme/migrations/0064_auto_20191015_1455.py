# Generated by Django 2.2.6 on 2019-10-15 13:55

import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0063_auto_20191014_1458"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheme",
            name="category",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="scheme.Category"),
        ),
        migrations.AlterField(
            model_name="scheme",
            name="linking_support",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=50),
                blank=True,
                default=list,
                help_text="journeys supported by the scheme in the ubiquity endpoints, ie: ADD, REGISTRATION, ENROL",
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="schemeaccount",
            name="balances",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name="schemeaccount",
            name="scheme",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="scheme.Scheme"),
        ),
        migrations.AlterField(
            model_name="schemeaccountimage",
            name="scheme",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="scheme.Scheme"
            ),
        ),
    ]
