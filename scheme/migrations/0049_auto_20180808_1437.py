# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-08-08 13:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0048_auto_20180712_1005'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'Pending'), (1, 'Active'), (403, 'Invalid credentials'), (432, 'Invalid mfa'), (530, 'End site down'), (531, 'IP blocked'), (532, 'Tripped captcha'), (5, 'Please check your scheme account login details.'), (434, 'Account locked on end site'), (429, 'Cannot connect, too many retries'), (503, 'Too many balance requests running'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable'), (10, 'Wallet only card'), (404, 'Agent does not exist on midas'), (533, 'Password expired'), (900, 'Join'), (444, 'No user currently found'), (536, 'Error with the configuration or it was not possible to retrieve'), (535, 'Request was not sent'), (445, 'Account already exists'), (537, 'Service connection error'), (401, 'Failed validation')], default=0),
        ),
    ]
