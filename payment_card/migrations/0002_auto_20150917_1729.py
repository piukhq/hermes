from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentcard",
            name="image",
            field=models.ImageField(upload_to="", default=1),
            preserve_default=False,
        ),
    ]
