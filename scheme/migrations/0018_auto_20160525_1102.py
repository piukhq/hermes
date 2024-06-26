# Generated by Django 1.9.2 on 2016-05-25 11:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0017_auto_20160523_0923"),
    ]

    operations = [
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
                    ("last_name", "last name"),
                    ("favourite_place", "favourite place"),
                    ("date_of_birth", "date_of_birth"),
                ],
                max_length=250,
            ),
        ),
    ]
