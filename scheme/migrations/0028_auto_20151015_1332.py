# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0027_auto_20151014_1316'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active'), (403, 'invalid credentials'), (432, 'invalid_mfa'), (530, 'end site down'), (4, 'deleted'), (5, 'incomplete'), (434, 'account locked on end site'), (429, 'Cannot connect, too many retries'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable'), (10, 'This is a wallet only card')], default=0),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='description',
            field=models.CharField(max_length=300, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='size_code',
            field=models.CharField(max_length=30, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='strap_line',
            field=models.CharField(max_length=50, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
