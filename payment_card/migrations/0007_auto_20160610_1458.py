# Generated by Django 1.9.2 on 2016-06-10 14:58

import django.db.models.deletion
import django.db.models.manager
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0006_auto_20160413_0849"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentCardImage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "image_type_code",
                    models.IntegerField(
                        choices=[
                            (0, "hero"),
                            (1, "banner"),
                            (2, "offers"),
                            (3, "icon"),
                            (4, "asset"),
                            (5, "reference"),
                            (6, "personal offers"),
                        ]
                    ),
                ),
                ("size_code", models.CharField(blank=True, max_length=30, null=True)),
                ("image", models.ImageField(upload_to="schemes")),
                ("strap_line", models.CharField(blank=True, max_length=50, null=True)),
                ("description", models.CharField(blank=True, max_length=300, null=True)),
                ("url", models.URLField(blank=True, null=True)),
                ("call_to_action", models.CharField(max_length=150)),
                ("order", models.IntegerField()),
                ("status", models.IntegerField(choices=[(0, "draft"), (1, "published")], default=0)),
                ("start_date", models.DateTimeField()),
                ("end_date", models.DateTimeField()),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "payment_card",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="payment_card.PaymentCard",
                    ),
                ),
            ],
            managers=[
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.AlterField(
            model_name="paymentcardaccountimage",
            name="image_type_code",
            field=models.IntegerField(
                choices=[
                    (0, "hero"),
                    (1, "banner"),
                    (2, "offers"),
                    (3, "icon"),
                    (4, "asset"),
                    (5, "reference"),
                    (6, "personal offers"),
                ]
            ),
        ),
    ]
