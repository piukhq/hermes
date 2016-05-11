# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_auto_20150911_1607'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetail',
            name='address_line_1',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='address_line_2',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='city',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='country',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='currency',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='first_name',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='last_name',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='notifications',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='pass_code',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='phone',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='postcode',
            field=models.CharField(blank=True, null=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='userdetail',
            name='region',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
    ]
