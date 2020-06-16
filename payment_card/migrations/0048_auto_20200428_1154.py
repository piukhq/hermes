# Generated by Django 2.2.11 on 2020-04-28 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0047_paymentaudit_payment_card_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='fingerprint',
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='token',
            field=models.CharField(max_length=255),
        )
    ]