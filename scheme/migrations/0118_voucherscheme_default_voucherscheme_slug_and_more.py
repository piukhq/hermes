# Generated by Django 4.2.3 on 2023-08-22 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheme", "0117_alter_schemeoverrideerror_error_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucherscheme",
            name="default",
            field=models.BooleanField(
                default=False, help_text="Default voucher scheme when multiple are available for a scheme"
            ),
        ),
        migrations.AddField(
            model_name="voucherscheme",
            name="slug",
            field=models.SlugField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="voucherscheme",
            constraint=models.UniqueConstraint(
                fields=("scheme", "slug"),
                name="unique_slug_per_scheme",
                violation_error_message="Each slug must be unique per Scheme",
            ),
        ),
        migrations.AddConstraint(
            model_name="voucherscheme",
            constraint=models.UniqueConstraint(
                condition=models.Q(("default", True)),
                fields=("scheme",),
                name="unique_default_per_scheme",
                violation_error_message="There can only be one default VoucherScheme per Scheme",
            ),
        ),
    ]
