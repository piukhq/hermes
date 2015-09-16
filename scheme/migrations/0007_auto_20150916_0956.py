# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0006_auto_20150915_1443'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemeaccount',
            name='is_valid',
        ),
        migrations.RemoveField(
            model_name='schemeimage',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='schemeimage',
            name='is_published',
        ),
        migrations.AddField(
            model_name='schemeimage',
            name='status',
            field=models.IntegerField(choices=[(0, 'draft'), (1, 'published')], default=0),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted')], default=0),
        ),
    ]
