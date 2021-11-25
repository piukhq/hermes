# Generated by Django 2.2.11 on 2020-06-04 15:06

import django.contrib.postgres.fields.jsonb
import django.utils.timezone
from django.db import migrations, models

import periodic_retry.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PeriodicRetry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "task_group",
                    models.CharField(
                        choices=[("retrytasks", "DEFAULT"), ("metis_request_retry_tasks", "METIS_REQUESTS")],
                        max_length=255,
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        choices=[(0, "REQUIRED"), (1, "PENDING"), (2, "SUCCESSFUL"), (3, "FAILED")],
                        default=periodic_retry.models.PeriodicRetryStatus(0),
                    ),
                ),
                ("module", models.CharField(max_length=64)),
                ("function", models.CharField(max_length=64)),
                ("data", django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True)),
                ("retry_count", models.IntegerField(blank=True, default=0, null=True)),
                ("max_retry_attempts", models.IntegerField(blank=True, null=True)),
                ("results", django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list, null=True)),
                ("next_retry_after", models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("modified_on", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
