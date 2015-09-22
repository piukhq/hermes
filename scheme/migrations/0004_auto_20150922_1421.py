# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0003_scheme_forgotten_password_url'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemeimage',
            name='identifier',
        ),
        migrations.RemoveField(
            model_name='schemeimage',
            name='is_barcode',
        ),
        migrations.AddField(
            model_name='scheme',
            name='identifier',
            field=models.CharField(max_length=30, default='id'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='scheme',
            name='is_barcode',
            field=models.BooleanField(default=0),
            preserve_default=False,
        ),
    ]
