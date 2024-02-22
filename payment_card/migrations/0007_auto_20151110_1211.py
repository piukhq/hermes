
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0006_auto_20151110_1130"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="pan_end",
            field=models.CharField(max_length=4),
        ),
        migrations.AlterField(
            model_name="paymentcardaccount",
            name="pan_start",
            field=models.CharField(max_length=6),
        ),
    ]
