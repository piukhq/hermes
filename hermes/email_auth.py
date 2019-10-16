from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings


class EmailBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, client_id=settings.BINK_CLIENT_ID, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        try:
            if username and "@" in username:
                user = UserModel.objects.get(client_id=client_id, email__iexact=username)
            else:
                user = UserModel._default_manager.get_by_natural_key(username)

            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            UserModel().set_password(password)
