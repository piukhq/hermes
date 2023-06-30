# Generated by Django 2.2.24 on 2021-11-17 13:33

from django.db import migrations, models

import scheme.models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0098_scheme_text_colour"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemeaccount",
            name="originating_journey",
            field=models.IntegerField(
                choices=[
                    (scheme.models.JourneyTypes(5), "Unknown"),
                    (scheme.models.JourneyTypes(0), "Enrol"),
                    (scheme.models.JourneyTypes(2), "Add"),
                    (scheme.models.JourneyTypes(4), "Register"),
                ],
                default=scheme.models.JourneyTypes(5),
            ),
        ),
    ]
