# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-02-12 11:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0054_auto_20190108_1502"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="schemecredentialquestion",
            name="field_type",
        ),
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="add_field",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="auth_field",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="enrol_field",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="register_field",
            field=models.BooleanField(default=False),
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
                ],
                default=0,
            ),
        ),
    ]
