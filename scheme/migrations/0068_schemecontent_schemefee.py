# Generated by Django 2.2.10 on 2020-03-11 11:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0067_auto_20200306_1257'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchemeFee',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fee_type', models.CharField(max_length=50)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=6)),
                ('scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme')),
            ],
        ),
        migrations.CreateModel(
            name='SchemeContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('column', models.CharField(max_length=50)),
                ('value', models.TextField()),
                ('scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme')),
            ],
        ),
    ]
