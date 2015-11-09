# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0032_auto_20151016_1620'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'Pending'), (1, 'Active'), (403, 'Invalid credentials'), (432, 'Invalid mfa'), (530, 'End site down'), (531, 'IP blocked'), (532, 'Tripped captcha'), (5, 'Incomplete'), (434, 'Account locked on end site'), (429, 'Cannot connect, too many retries'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable'), (10, 'Wallet only card'), (404, 'Agent does not exist on midas'), (533, 'Password expired')]),
        ),
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('last_name', 'last name')], max_length=250),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(choices=[('username', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('place_of_birth', 'place of birth'), ('postcode', 'postcode'), ('memorable_date', 'memorable date'), ('pin', 'pin'), ('last_name', 'last name')], max_length=250),
        ),
    ]
