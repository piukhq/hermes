# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0016_auto_20151007_1632'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'pending'), (1, 'active'), (403, 'invalid credentials'), (432, 'invalid_mfa'), (530, 'end site down'), (4, 'deleted'), (5, 'incomplete'), (434, 'account locked on end site'), (429, 'Cannot connect, too many retries'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable')]),
        ),
    ]
