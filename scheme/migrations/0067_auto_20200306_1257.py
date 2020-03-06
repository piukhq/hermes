# Generated by Django 2.2.7 on 2020-03-06 12:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0066_auto_20200127_1726'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucherscheme',
            name='body_text_expired',
            field=models.TextField(blank=True, verbose_name='Expired'),
        ),
        migrations.AddField(
            model_name='voucherscheme',
            name='body_text_inprogress',
            field=models.TextField(blank=True, verbose_name='In Progress'),
        ),
        migrations.AddField(
            model_name='voucherscheme',
            name='body_text_issued',
            field=models.TextField(blank=True, verbose_name='Issued'),
        ),
        migrations.AddField(
            model_name='voucherscheme',
            name='body_text_redeemed',
            field=models.TextField(blank=True, verbose_name='Redeemed'),
        ),
        migrations.AddField(
            model_name='voucherscheme',
            name='terms_and_conditions_url',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='voucherscheme',
            name='earn_type',
            field=models.CharField(choices=[('join', 'Join'), ('accumulator', 'Accumulator'), ('stamps', 'Stamps')], max_length=50, verbose_name='Earn Type'),
        ),
        migrations.AlterField(
            model_name='voucherscheme',
            name='subtext',
            field=models.CharField(blank=True, max_length=250),
        ),
    ]
