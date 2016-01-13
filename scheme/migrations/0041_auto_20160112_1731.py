# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0040_auto_20160112_1727'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='schemeaccountcredentialanswer',
            unique_together=set([('scheme_account', 'question')]),
        ),
    ]
