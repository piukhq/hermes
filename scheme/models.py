from django.db import models
from user.models import CustomUser


class Scheme(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()
    company = models.CharField(max_length=200)
    company_url = models.URLField()
    forgotten_password_url = models.URLField
    tier = models.IntegerField()
    barcode_type = models.IntegerField()
    scan_message = models.CharField(max_length=100)
    point_name = models.CharField(max_length=50, default='points')
    point_conversion_rate = models.DecimalField(max_digits=20, decimal_places=10)
    input_label = models.CharField(max_length=150)  # CARD PREFIX
    is_active = models.BooleanField(default=True)


class SchemeImage(models.Model):
    scheme_id = models.ForeignKey('scheme.Scheme')
    image_type_code = models.IntegerField()
    is_barcode = models.BooleanField()
    identifier = models.CharField(max_length=30)
    size_code = models.CharField(max_length=30)
    image_path = models.CharField(max_length=300)
    strap_line = models.CharField(max_length=50)
    description = models.CharField(max_length=300)
    url = models.URLField()
    call_to_action = models.CharField(max_length=50)
    order = models.IntegerField()
    #TODO: Sort the overlapping nature of these
    is_published = models.BooleanField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_deleted = models.BooleanField()
    created = models.DateTimeField()


class SchemeAccount(models.Model):
    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    username = models.CharField(max_length=150)
    card_number = models.CharField(max_length=50)
    membership_number = models.CharField(max_length=50)
    password = models.CharField(max_length=30)
    status = models.IntegerField()
    order = models.IntegerField()
    is_valid = models.BooleanField()
    created = models.DateTimeField()
    updated = models.DateTimeField()


class SchemeAccountSecurityQuestion(models.Model):
    scheme_account_id = models.ForeignKey(SchemeAccount)
    question = models.CharField(max_length=250)
    answer = models.CharField(max_length=250)



