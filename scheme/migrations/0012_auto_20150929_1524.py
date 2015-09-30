# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0011_auto_20150928_0907'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='order',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted'), (5, 'incomplete')], default=5),
        ),
    ]
