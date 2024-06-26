# Generated by Django 4.2.10 on 2024-04-16 08:56

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scripts", "0016_alter_filescript_correction_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="filescript",
            name="correction",
            field=models.IntegerField(
                choices=[(0, "No correction available"), (7001, "Right to be forgotten"), (8001, "Account closure")],
                db_index=True,
                help_text="Correction Required",
            ),
        ),
    ]
