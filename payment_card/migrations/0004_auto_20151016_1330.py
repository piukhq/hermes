from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0003_auto_20150923_1044"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="pan",
            field=models.CharField(max_length=50),
        ),
    ]
