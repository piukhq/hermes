# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-06-18 14:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0059_auto_20190510_1125'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='answer_type',
            field=models.IntegerField(choices=[(0, 'text'), (1, 'sensitive'), (2, 'choice'), (3, 'boolean'), (4, 'payment_card_id')], default=0),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('title', 'title'), ('first_name', 'first name'), ('last_name', 'last name'), ('favourite_place', 'favourite place'), ('date_of_birth', 'date_of_birth'), ('phone', 'phone number'), ('phone_2', 'phone number 2'), ('gender', 'gender'), ('address_1', 'address 1'), ('address_2', 'address 2'), ('address_3', 'address 3'), ('town_city', 'town city'), ('county', 'county'), ('country', 'country'), ('regular_restaurant', 'regular restaurant'), ('merchant_identifier', 'merchant identifier'), ('payment_card_id', 'payment_card_id')], max_length=250),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestionchoice',
            name='scheme_question',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('title', 'title'), ('first_name', 'first name'), ('last_name', 'last name'), ('favourite_place', 'favourite place'), ('date_of_birth', 'date_of_birth'), ('phone', 'phone number'), ('phone_2', 'phone number 2'), ('gender', 'gender'), ('address_1', 'address 1'), ('address_2', 'address 2'), ('address_3', 'address 3'), ('town_city', 'town city'), ('county', 'county'), ('country', 'country'), ('regular_restaurant', 'regular restaurant'), ('merchant_identifier', 'merchant identifier'), ('payment_card_id', 'payment_card_id')], max_length=250),
        ),
    ]
