import factory
from user import models
from faker import Factory


fake = Factory.create()


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.CustomUser

    email = fake.email()
    is_active = True
    is_staff = False

