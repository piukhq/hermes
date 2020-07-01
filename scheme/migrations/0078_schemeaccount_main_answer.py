# Generated by Django 2.2.11 on 2020-06-22 15:01
from django.db import migrations, models
from django.db.models import Q


def populate_main_answer(apps, schema_editor):
    SchemeAccount = apps.get_model("scheme", "SchemeAccount")
    SchemeAccountCredentialAnswer = apps.get_model("scheme", "SchemeAccountCredentialAnswer")

    answers = SchemeAccountCredentialAnswer.objects.filter(
        Q(question__manual_question=True) | Q(question__scan_question=True), scheme_account__is_deleted=False
    ).prefetch_related("scheme_account")

    accounts = []
    for answer in answers:
        account = answer.scheme_account
        account.main_answer = answer.answer
        accounts.append(account)

    SchemeAccount.objects.bulk_update(accounts, ["main_answer"], batch_size=1000)


def revert_populate_main_answer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("scheme", "0077_scheme_formatted_images")]

    operations = [
        migrations.AddField(
            model_name="schemeaccount",
            name="main_answer",
            field=models.CharField(blank=True, default="", max_length=250),
        ),
        migrations.RunPython(populate_main_answer, revert_populate_main_answer),
    ]
