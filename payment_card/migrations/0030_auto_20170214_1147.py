# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-02-14 11:47
from __future__ import unicode_literals

from django.db import migrations
from django.conf import settings


def apply_barclays_images(apps, schema_editor):
    PaymentCardAccount = apps.get_model('payment_card', 'PaymentCardAccount')
    PaymentCardAccountImage = apps.get_model('payment_card', 'PaymentCardAccountImage')

    barclays_offer_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                               image_type_code=2)
    for account in PaymentCardAccount.all_objects.all():
        if account.pan_start in settings.BARCLAYS_BINS:
            barclays_offer_image.payment_card_accounts.add(account)

            try:
                barclays_hero_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                          image_type_code=0,
                                                                          payment_card=account.payment_card)
            except PaymentCardAccountImage.DoesNotExist:
                # not a barclays card that we have an image for, so don't add it.
                pass
            else:
                barclays_hero_image.payment_card_accounts.add(account)


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0029_auto_20170113_1136'),
    ]

    operations = [
        migrations.RunPython(apply_barclays_images),
    ]
