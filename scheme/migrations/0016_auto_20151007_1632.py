# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0015_auto_20151006_1632'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('password', 'password'), ('date_of_birth', 'date of birth')], max_length=250),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('password', 'password'), ('date_of_birth', 'date of birth')], max_length=250),
        ),
    ]
