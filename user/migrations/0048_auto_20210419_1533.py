# Generated by Django 2.2.19 on 2021-04-19 14:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0047_clientapplicationbundle_external_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientapplicationbundle',
            name='email_from',
            field=models.EmailField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='clientapplicationbundle',
            name='subject',
            field=models.CharField(blank=True, default='Magic Link Request', max_length=100),
        ),
    ]