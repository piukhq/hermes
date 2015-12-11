# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0034_remove_scheme_point_conversion_rate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('last_name', 'last name'), ('favourite_place', 'favourite place')], max_length=250),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('last_name', 'last name'), ('favourite_place', 'favourite place')], max_length=250),
        ),
    ]
