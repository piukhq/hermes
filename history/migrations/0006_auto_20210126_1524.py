# Generated by Django 2.2.14 on 2021-01-26 15:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("history", "0005_historicalvopactivation"),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalPaymentCardSchemeEntry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "change_type",
                    models.CharField(
                        choices=[("create", "create"), ("update", "update"), ("delete", "delete")], max_length=6
                    ),
                ),
                ("instance_id", models.CharField(max_length=255)),
                ("channel", models.CharField(max_length=255)),
                ("change_details", models.CharField(blank=True, max_length=255)),
                ("user_id", models.IntegerField(null=True)),
                ("scheme_account_id", models.IntegerField()),
                ("payment_card_account_id", models.IntegerField()),
                ("active_link", models.BooleanField()),
            ],
            options={
                "verbose_name": "Historical Scheme account to Payment card account association",
            },
        ),
        migrations.AlterModelOptions(
            name="historicalpaymentcardaccountentry",
            options={"verbose_name": "Historical Payment card account to User association"},
        ),
        migrations.AlterModelOptions(
            name="historicalschemeaccountentry",
            options={"verbose_name": "Historical Scheme account to User association"},
        ),
    ]
