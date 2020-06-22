# Generated by Django 2.2.11 on 2020-06-22 15:01
from functools import lru_cache

from django.db import migrations, models


@lru_cache(maxsize=256)
def get_main_question_type(scheme):
    return scheme.questions.filter(manual_question=True).values_list('id', flat=True).first()


def get_manual_answer(scheme_account):
    question_id = get_main_question_type(scheme_account.scheme)
    return scheme_account.schemeaccountcredentialanswer_set.filter(
        question=question_id
    ).values_list('answer', flat=True).get()


def populate_main_answer(apps, schema_editor):
    SchemeAccount = apps.get_model('scheme', 'SchemeAccount')

    for account in SchemeAccount.all_objects.filter(is_deleted=False).all():
        account.main_answer = get_manual_answer(account)
        account.save(update_fields=['main_answer'])


def revert_populate_main_answer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('scheme', '0076_format_stored_balance'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemeaccount',
            name='main_answer',
            field=models.CharField(blank=True, default='', max_length=250),
        ),
        migrations.RunPython(populate_main_answer, revert_populate_main_answer),
    ]
