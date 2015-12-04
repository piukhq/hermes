# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import colorful.fields


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0035_auto_20151126_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='colour',
            field=colorful.fields.RGBColorField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'Pending'), (1, 'Active'), (403, 'Invalid credentials'), (432, 'Invalid mfa'), (530, 'End site down'), (531, 'IP blocked'), (532, 'Tripped captcha'), (5, 'Please check your scheme account login details.'), (434, 'Account locked on end site'), (429, 'Cannot connect, too many retries'), (520, 'An unknown error has occurred'), (9, 'Midas unavailable'), (10, 'Wallet only card'), (404, 'Agent does not exist on midas'), (533, 'Password expired')]),
        ),
    ]
