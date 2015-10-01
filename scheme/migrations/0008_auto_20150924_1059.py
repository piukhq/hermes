# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import scheme.models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0007_auto_20150923_1403'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchemeAccountCredentialAnswer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('answer', models.CharField(max_length=250)),
            ],
        ),
        migrations.CreateModel(
            name='SchemeCredentialQuestion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('slug', models.SlugField()),
                ('question', models.CharField(max_length=250)),
                ('scheme', models.ForeignKey(to='scheme.Scheme')),
            ],
        ),
        migrations.RemoveField(
            model_name='schemeaccountsecurityquestion',
            name='scheme_account',
        ),
        migrations.DeleteModel(
            name='SchemeAccountSecurityQuestion',
        ),
        migrations.AddField(
            model_name='schemeaccountcredentialanswer',
            name='question',
            field=models.ForeignKey(to='scheme.SchemeCredentialQuestion'),
        ),
        migrations.AddField(
            model_name='schemeaccountcredentialanswer',
            name='scheme_account',
            field=models.ForeignKey(to='scheme.SchemeAccount'),
        ),
    ]
