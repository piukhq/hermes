# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0025_auto_20151014_1028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='point_name',
            field=models.CharField(blank=True, default='points', max_length=50, null=True),
        ),
    ]
