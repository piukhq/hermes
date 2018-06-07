# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-06-07 09:52
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scheme', '0041_auto_20180504_1519'),
    ]

    operations = [
        migrations.CreateModel(
            name='Consent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_box', models.BooleanField()),
                ('text', models.CharField(max_length=500)),
                ('is_enabled', models.BooleanField(default=True)),
                ('required', models.BooleanField()),
                ('order', models.IntegerField()),
                ('journey', models.IntegerField(choices=[(0, 'join'), (1, 'link')])),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme')),
            ],
        ),
        migrations.CreateModel(
            name='UserConsent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('value', models.BooleanField()),
                ('consent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_consent', to='scheme.Consent')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_consent', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
