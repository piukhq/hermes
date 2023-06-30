# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-11-28 10:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0036_auto_20171030_1205"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="schemecredentialquestion",
            name="join_question",
        ),
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="options",
            field=models.IntegerField(choices=[(0, "None"), (1, "Link"), (2, "Join"), (3, "Link & Join")], default=0),
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
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (444, "No user currently found"),
                ],
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="schemecredentialquestion",
            name="type",
            field=models.CharField(
                choices=[
                    ("username", "user name"),
                    ("email", "email"),
                    ("card_number", "card number"),
                    ("barcode", "barcode"),
                    ("password", "password"),
                    ("place_of_birth", "place of birth"),
                    ("postcode", "postcode"),
                    ("memorable_date", "memorable date"),
                    ("pin", "pin"),
                    ("title", "title"),
                    ("first_name", "first name"),
                    ("last_name", "last name"),
                    ("favourite_place", "favourite place"),
                    ("date_of_birth", "date_of_birth"),
                    ("phone", "phone number"),
                ],
                max_length=250,
            ),
        ),
    ]
