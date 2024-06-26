# Generated by Django 4.0.3 on 2022-03-08 16:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scripts", "0004_auto_20220208_1342"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scriptresult",
            name="apply",
            field=models.IntegerField(
                choices=[
                    (0, "No correction available"),
                    (1, "Mark as deactivated as same token is also active"),
                    (2, "VOP Activate"),
                    (3, "Re-enrol, VOP Deactivate, Un-enroll"),
                    (4, "Re-enroll"),
                    (5, "VOP Deactivate"),
                    (6, "Un-enroll"),
                    (7, "Fix-enroll"),
                    (8, "Retain"),
                    (9, "Retain, Fix-Enroll"),
                    (10, "Un-enroll, Re-Enroll, Set Active"),
                    (11, "Set Active"),
                    (1001, "Mark as Unknown"),
                    (1002, "Refresh Balance"),
                ],
                db_index=True,
                default=0,
                help_text="Correction to Apply Now",
            ),
        ),
        migrations.AlterField(
            model_name="scriptresult",
            name="correction",
            field=models.IntegerField(
                choices=[
                    (0, "No correction available"),
                    (1, "Mark as deactivated as same token is also active"),
                    (2, "VOP Activate"),
                    (3, "Re-enrol, VOP Deactivate, Un-enroll"),
                    (4, "Re-enroll"),
                    (5, "VOP Deactivate"),
                    (6, "Un-enroll"),
                    (7, "Fix-enroll"),
                    (8, "Retain"),
                    (9, "Retain, Fix-Enroll"),
                    (10, "Un-enroll, Re-Enroll, Set Active"),
                    (11, "Set Active"),
                    (1001, "Mark as Unknown"),
                    (1002, "Refresh Balance"),
                ],
                db_index=True,
                default=0,
                help_text="Correction Required",
            ),
        ),
        migrations.AlterField(
            model_name="scriptresult",
            name="data",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name="scriptresult",
            name="results",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
