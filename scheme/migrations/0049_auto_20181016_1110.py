# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-10-16 10:10
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ubiquity', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scheme', '0048_auto_20181016_1110'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemeaccount',
            name='user_set',
            field=models.ManyToManyField(related_name='scheme_account_set', through='ubiquity.SchemeAccountEntry', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='schemeaccountimage',
            name='encoding',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='answer_type',
            field=models.IntegerField(choices=[(0, 'text'), (1, 'sensitive'), (2, 'choice'), (3, 'boolean')], default=0),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='choice',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), blank=True, null=True, size=None),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='description',
            field=models.CharField(blank=True, default='', max_length=250),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='field_type',
            field=models.IntegerField(blank=True, choices=[(0, 'add'), (1, 'auth'), (2, 'enrol')], null=True),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='validation',
            field=models.TextField(blank=True, default='', max_length=250),
        ),
        migrations.AddField(
            model_name='schemeimage',
            name='encoding',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='schemedetail',
            name='scheme_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme'),
        ),
        migrations.AddField(
            model_name='schemebalancedetails',
            name='scheme_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme'),
        ),
    ]
