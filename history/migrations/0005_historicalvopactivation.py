# Generated by Django 2.2.14 on 2021-01-26 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('history', '0004_historicalcustomuser'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalVopActivation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('change_type', models.CharField(choices=[('create', 'create'), ('update', 'update'), ('delete', 'delete')], max_length=6)),
                ('instance_id', models.CharField(max_length=255)),
                ('channel', models.CharField(max_length=255)),
                ('change_details', models.CharField(blank=True, max_length=255)),
                ('user_id', models.IntegerField(null=True)),
                ('scheme_id', models.IntegerField()),
                ('payment_card_account_id', models.IntegerField()),
                ('status', models.IntegerField()),
                ('activation_id', models.CharField(blank=True, default='', max_length=60)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
