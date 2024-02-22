# Generated by Django 1.11.7 on 2019-01-08 16:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0054_auto_20190108_1502"),
        ("payment_card", "0039_paymentcarduserassociation"),
        ("user", "0032_auto_20181107_1158"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="organisation",
            name="issuers",
        ),
        migrations.RemoveField(
            model_name="organisation",
            name="schemes",
        ),
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="issuers",
            field=models.ManyToManyField(blank=True, to="payment_card.Issuer"),
        ),
        migrations.AddField(
            model_name="clientapplicationbundle",
            name="schemes",
            field=models.ManyToManyField(blank=True, to="scheme.Scheme"),
        ),
    ]
