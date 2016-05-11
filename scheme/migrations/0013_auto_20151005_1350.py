# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0012_auto_20150929_1524'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='schemeaccount',
            options={'ordering': ['order']},
        ),
        migrations.AlterModelOptions(
            name='schemecredentialquestion',
            options={'ordering': ['order']},
        ),
        migrations.AlterField(
            model_name='scheme',
            name='slug',
            field=models.SlugField(unique=True, choices=[('tesco', 'Tesco'), ('advantage-card', 'Boots'), ('superdrug', 'Superdrug'), ('shell', 'Shell'), ('morrisons', 'Morrisons'), ('kfc', 'Kfc'), ('costa', 'Costa'), ('cooperative', 'Cooperative')]),
        ),
        migrations.AlterField(
            model_name='schemeaccount',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted'), (5, 'incomplete'), (6, 'account locked on end site'), (7, 'Cannot connect, too many retries'), (8, 'An unknown error has occurred')]),
        ),
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(max_length=250, choices=[('user_name', 'user_name'), ('card_number', 'card_number'), ('password', 'password'), ('date_of_birth', 'date_of_birth')]),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(max_length=250, choices=[('user_name', 'user_name'), ('card_number', 'card_number'), ('password', 'password'), ('date_of_birth', 'date_of_birth')]),
        ),
        migrations.AlterField(
            model_name='schemeimage',
            name='scheme',
            field=models.ForeignKey(to='scheme.Scheme', related_name='images'),
        ),
    ]
