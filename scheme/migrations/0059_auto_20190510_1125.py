# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-05-10 10:25
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0034_auto_20190109_1026"),
        ("scheme", "0058_scheme_linking_support"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThirdPartyConsentLink",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("consent_label", models.CharField(max_length=50)),
                ("add_field", models.BooleanField(default=False)),
                ("auth_field", models.BooleanField(default=False)),
                ("register_field", models.BooleanField(default=False)),
                ("enrol_field", models.BooleanField(default=False)),
                (
                    "client_app",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="client_app",
                        to="user.ClientApplication",
                    ),
                ),
                (
                    "consent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="consent", to="scheme.Consent"
                    ),
                ),
                (
                    "scheme",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="scheme", to="scheme.Scheme"
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="schemeaccount",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "Pending"),
                    (1, "Active"),
                    (403, "Invalid credentials"),
                    (432, "Invalid mfa"),
                    (530, "End site down"),
                    (531, "IP blocked"),
                    (532, "Tripped captcha"),
                    (5, "Please check your scheme account login details."),
                    (434, "Account locked on end site"),
                    (429, "Cannot connect, too many retries"),
                    (503, "Too many balance requests running"),
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (444, "No user currently found"),
                    (536, "Error with the configuration or it was not possible to retrieve"),
                    (535, "Request was not sent"),
                    (445, "Account already exists"),
                    (537, "Service connection error"),
                    (401, "Failed validation"),
                    (406, "Pre-registered card"),
                    (446, "Update failed. Delete and re-add card."),
                    (204, "Pending manual check."),
                    (436, "Invalid card_number"),
                    (437, "You can only Link one card per day."),
                    (438, "Unknown Card number"),
                    (439, "General Error such as incorrect user details"),
                    (441, "Join in progress"),
                    (538, "A system error occurred during join"),
                    (447, "The scheme has requested this account should be deleted"),
                    (442, "Asynchronous join in progress"),
                ],
                default=0,
            ),
        ),
    ]
