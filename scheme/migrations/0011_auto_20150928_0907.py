# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0010_auto_20150925_1304'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemeaccount',
            name='card_number',
        ),
        migrations.RemoveField(
            model_name='schemeaccount',
            name='membership_number',
        ),
        migrations.RemoveField(
            model_name='schemeaccount',
            name='password',
        ),
        migrations.RemoveField(
            model_name='schemeaccount',
            name='username',
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted'), (5, 'incomplete')], default=0),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='scheme',
            field=models.ForeignKey(to='scheme.Scheme', related_name='questions'),
        ),
    ]
