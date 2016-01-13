# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0038_auto_20160108_1459'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemeaccountcredentialanswer',
            name='type',
        ),
    ]
