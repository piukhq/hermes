# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0028_auto_20151015_1332'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemeaccount',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'pending'), (1, 'active'), (403, 'invalid credentials'), (432, 'invalid_mfa'), (530, 'end site down'), (5, 'incomplete'), (434, 'account locked on end site'), (429, 'Cannot connect, too many retries'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable'), (10, 'This is a wallet only card')]),
        ),
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(max_length=250, choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('date_of_birth', 'date of birth'), ('postcode', 'postcode')]),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(max_length=250, choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('date_of_birth', 'date of birth'), ('postcode', 'postcode')]),
        ),
    ]
