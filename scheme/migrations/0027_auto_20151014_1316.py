# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0026_auto_20151014_1030'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheme',
            name='is_barcode',
        ),
        migrations.AlterField(
            model_name='scheme',
            name='identifier',
            field=models.CharField(blank=True, null=True, max_length=30, help_text='Regex identifier for barcode'),
        ),
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('date_of_birth', 'date of birth')], max_length=250),
        ),
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(choices=[('user_name', 'user name'), ('email', 'email'), ('card_number', 'card number'), ('barcode', 'barcode'), ('password', 'password'), ('date_of_birth', 'date of birth')], max_length=250),
        ),
    ]
