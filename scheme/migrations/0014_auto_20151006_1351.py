# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0013_auto_20151005_1350'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted'), (5, 'incomplete'), (6, 'account locked on end site'), (7, 'Cannot connect, too many retries'), (8, 'An unknown error has occurred'), (9, 'Midas unavailable')], default=0),
        ),
    ]
