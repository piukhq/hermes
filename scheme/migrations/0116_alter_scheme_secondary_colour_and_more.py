# Generated by Django 4.2.2 on 2023-07-05 13:16

import re

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0115_schemecredentialquestion_is_optional"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheme",
            name="secondary_colour",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Hex string e.g "#112233"',
                max_length=7,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#((?:[0-9a-fA-F]{3}){1,2})$"),
                        "Enter a valid 'colour' in hexadecimal format e.g \"#112233\"",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="scheme",
            name="text_colour",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Hex string e.g "#112233"',
                max_length=7,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#((?:[0-9a-fA-F]{3}){1,2})$"),
                        "Enter a valid 'colour' in hexadecimal format e.g \"#112233\"",
                    )
                ],
            ),
        ),
    ]
