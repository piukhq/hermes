from urllib.parse import urlencode

from django.contrib.auth.models import Group
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect
from django.utils.crypto import get_random_string
from mozilla_django_oidc.auth import LOGGER, OIDCAuthenticationBackend
from mozilla_django_oidc.utils import add_state_and_nonce_to_session
from mozilla_django_oidc.views import OIDCAuthenticationRequestView, get_next_url

from user.models import ClientApplication, CustomUser


class SSOAuthBackend(OIDCAuthenticationBackend):
    # This is lifted so we can get access to `payload`
    def get_or_create_user(self, access_token, id_token, payload):
        """Returns a User instance if 1 user is found. Creates a user if not found
        and configured to do so. Returns nothing if multiple users are matched."""

        user_info = self.get_userinfo(access_token, id_token, payload)

        email = user_info.get("email")

        claims_verified = self.verify_claims(user_info)
        if not claims_verified:
            raise SuspiciousOperation("Claims verification failed")

        if not email:
            raise SuspiciousOperation("No email found in user_info, cant authenticate with Django users")

        # email based filtering, we also filter client application and external id
        # this avoids returning multiple users across different client applications or different external ids
        bink_client = ClientApplication.get_bink_app()
        users = CustomUser.objects.filter(email=email, client=bink_client, external_id="")

        if len(users) == 1:
            return self.update_user(users[0], user_info, payload)
        elif len(users) > 1:
            # In the rare case that two user accounts have the same email address,
            # bail. Randomly selecting one seems really wrong.
            raise SuspiciousOperation("Multiple users returned")
        elif self.get_settings("OIDC_CREATE_USER", True):
            user = self.create_user(user_info, payload)
            return user
        else:
            LOGGER.debug("Login failed: No user with email %s found, and " "OIDC_CREATE_USER is False", email)
            return None

    def create_user(self, claims, payload):
        bink_client = ClientApplication.get_bink_app()
        email = claims.get("email")
        user = self.UserModel.objects.create_user(email, client=bink_client, external_id="")
        self._fixup_perms(user, payload)
        return user

    def update_user(self, user, claims, payload):
        self._fixup_perms(user, payload)
        return user

    def _fixup_perms(self, user, payload):
        user.is_staff = True
        user.is_superuser = False

        rw = Group.objects.get(name="Read/Write")
        ro = Group.objects.get(name="Read Only")

        # Get roles from AAD token
        roles = payload.get("roles", [])
        if len(roles) != 1:
            roles = ["readonly"]
        role = roles[0]

        if role == "superuser":
            user.is_superuser = True
        elif role == "readwrite":
            user.is_superuser = False
            ro.user_set.remove(user)
            user.user_permissions.clear()
            rw.user_set.add(user)

        else:
            user.is_superuser = False
            rw.user_set.remove(user)
            user.user_permissions.clear()
            ro.user_set.add(user)

        user.save()

    def authenticate(self, request, **kwargs):
        """Authenticates a user based on the OIDC code flow."""

        self.request = request
        if not self.request:
            return None

        state = self.request.GET.get("state")
        code = self.request.GET.get("code")
        nonce = kwargs.pop("nonce", None)

        if not code or not state:
            return None

        reply_url = self.get_settings("OIDC_RP_REPLY_URL")

        token_payload = {
            "client_id": self.OIDC_RP_CLIENT_ID,
            "client_secret": self.OIDC_RP_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": reply_url,
        }

        # Get the token
        token_info = self.get_token(token_payload)
        id_token = token_info.get("id_token")
        access_token = token_info.get("access_token")

        # Validate the token
        payload = self.verify_token(id_token, nonce=nonce)

        if payload:
            self.store_tokens(access_token, id_token)
            try:
                return self.get_or_create_user(access_token, id_token, payload)
            except SuspiciousOperation as exc:
                LOGGER.warning("failed to get or create user: %s", exc)
                return None

        return None


# The absolute url function does not take into account the X-Forwarded headers :/
class CustomOIDCAuthenticationRequestView(OIDCAuthenticationRequestView):
    def get(self, request):
        """OIDC client authentication initialization HTTP endpoint"""
        state = get_random_string(self.get_settings("OIDC_STATE_SIZE", 32))
        redirect_field_name = self.get_settings("OIDC_REDIRECT_FIELD_NAME", "next")
        reply_url = self.get_settings("OIDC_RP_REPLY_URL")
        params = {
            "response_type": "code",
            "scope": self.get_settings("OIDC_RP_SCOPES", "openid email"),
            "client_id": self.OIDC_RP_CLIENT_ID,
            "redirect_uri": reply_url,
            "state": state,
        }

        params.update(self.get_extra_params(request))

        if self.get_settings("OIDC_USE_NONCE", True):
            nonce = get_random_string(self.get_settings("OIDC_NONCE_SIZE", 32))
            params.update({"nonce": nonce})

        add_state_and_nonce_to_session(request, state, params)

        request.session["oidc_login_next"] = get_next_url(request, redirect_field_name)

        query = urlencode(params)
        redirect_url = "{url}?{query}".format(url=self.OIDC_OP_AUTH_ENDPOINT, query=query)
        return HttpResponseRedirect(redirect_url)
