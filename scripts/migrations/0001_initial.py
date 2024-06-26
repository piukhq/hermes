# Generated by Django 2.2.14 on 2020-11-04 04:03

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ScriptResult",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True)),
                ("results", django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list, null=True)),
                (
                    "correction",
                    models.IntegerField(
                        choices=[
                            (0, "No correction available"),
                            (1, "Mark as deactivated as same token is also active"),
                            (2, "Transfer activation to card with same token"),
                            (3, "Re-enrol, Deactivate, Un-enroll"),
                            (4, "Re-enroll"),
                            (5, "Deactivate"),
                            (6, "Un-enroll"),
                        ],
                        db_index=True,
                        default=0,
                        help_text="Correction Required",
                    ),
                ),
                ("done", models.BooleanField(default=False)),
                ("script_name", models.CharField(default="unknown", max_length=100)),
                (
                    "apply",
                    models.IntegerField(
                        choices=[
                            (0, "No correction available"),
                            (1, "Mark as deactivated as same token is also active"),
                            (2, "Transfer activation to card with same token"),
                            (3, "Re-enrol, Deactivate, Un-enroll"),
                            (4, "Re-enroll"),
                            (5, "Deactivate"),
                            (6, "Un-enroll"),
                        ],
                        db_index=True,
                        default=0,
                        help_text="Correction to Apply Now",
                    ),
                ),
                ("item_id", models.CharField(default="unknown", max_length=100)),
            ],
        ),
    ]
