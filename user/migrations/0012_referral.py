# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0011_userdetail_gender'),
    ]

    operations = [
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.OneToOneField(to=settings.AUTH_USER_MODEL, related_name='recipient')),
                ('referrer', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='referrer')),
            ],
        ),
    ]
