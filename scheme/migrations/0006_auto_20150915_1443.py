# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0005_auto_20150915_1409'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccount',
            name='password',
            field=models.TextField(),
        ),
    ]
