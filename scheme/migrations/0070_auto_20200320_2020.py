# Generated by Django 2.2.11 on 2020-03-20 20:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0069_auto_20200316_1104"),
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
                    ("title", "title"),
                    ("first_name", "first name"),
                    ("last_name", "last name"),
                    ("favourite_place", "favourite place"),
                    ("date_of_birth", "date_of_birth"),
                    ("phone", "phone number"),
                    ("phone_2", "phone number 2"),
                    ("gender", "gender"),
                    ("address_1", "address 1"),
                    ("address_2", "address 2"),
                    ("address_3", "address 3"),
                    ("town_city", "town city"),
                    ("county", "county"),
                    ("country", "country"),
                    ("regular_restaurant", "regular restaurant"),
                    ("merchant_identifier", "merchant identifier"),
                    ("payment_card_hash", "payment_card_hash"),
                ],
                max_length=250,
            ),
        ),
        migrations.AlterField(
            model_name="schemecredentialquestionchoice",
            name="scheme_question",
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
                    ("phone_2", "phone number 2"),
                    ("gender", "gender"),
                    ("address_1", "address 1"),
                    ("address_2", "address 2"),
                    ("address_3", "address 3"),
                    ("town_city", "town city"),
                    ("county", "county"),
                    ("country", "country"),
                    ("regular_restaurant", "regular restaurant"),
                    ("merchant_identifier", "merchant identifier"),
                    ("payment_card_hash", "payment_card_hash"),
                ],
                max_length=250,
            ),
        ),
    ]
