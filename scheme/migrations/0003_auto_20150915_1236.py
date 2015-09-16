# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0002_schemeaccount_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='slug',
            field=models.SlugField(default='', unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='scheme',
            name='tier',
            field=models.IntegerField(choices=[('Tier 1', 1), ('Tier 2', 2)]),
        ),
    ]
