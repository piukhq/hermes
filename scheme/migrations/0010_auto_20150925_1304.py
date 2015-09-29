# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0009_auto_20150924_1239'),
    ]

    operations = [
        migrations.RenameField(
            model_name='schemecredentialquestion',
            old_name='question',
            new_name='label',
        ),
        migrations.RemoveField(
            model_name='scheme',
            name='input_label',
        ),
        migrations.RemoveField(
            model_name='schemeaccountcredentialanswer',
            name='question',
        ),
        migrations.RemoveField(
            model_name='schemecredentialquestion',
            name='slug',
        ),
        migrations.AddField(
            model_name='scheme',
            name='primary_question',
            field=models.ForeignKey(to='scheme.SchemeCredentialQuestion', related_name='primary_question', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='schemeaccountcredentialanswer',
            name='type',
            field=models.CharField(default='username', choices=[('username', 'username'), ('card_number', 'card_number'), ('password', 'password'), ('date_of_birth', 'date_of_birth')], max_length=250),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='type',
            field=models.CharField(default='username', choices=[('username', 'username'), ('card_number', 'card_number'), ('password', 'password'), ('date_of_birth', 'date_of_birth')], max_length=250),
            preserve_default=False,
        ),
    ]
