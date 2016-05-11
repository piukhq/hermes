# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings

from django.db import models, migrations
from scheme.encyption import AESCipher


def encrypt_scheme_account_passwords(apps, scheme_editor):
    SchemeAccountAnswer = apps.get_model("scheme", "SchemeAccountCredentialAnswer")
    for answer in SchemeAccountAnswer.objects.all():
        if answer.type == "password":
            encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(answer.answer).decode("utf-8")
            answer.answer = encrypted_answer
            answer.save()

class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0031_merge'),
    ]

    operations = [
        migrations.RunPython(encrypt_scheme_account_passwords),
    ]
