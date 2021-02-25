import arrow
import jwt


class GenerateJWToken:
    """
    Generates JWTokens for ubiquity endpoints authorisation and access tokens for magic links user creation.

    **Usage examples:**

        **Bearer tokens:**

            GenerateJWToken(
                organisation_id="Loyalty Angels",
                client_secret="8vA/fjVA83(n05LWh7R4'$3dWmVCU",
                bundle_id="com.bink.wallet",
                email="test@user.mail"
            ).get_token()

        **Magic Link temporary tokens:**

            GenerateJWToken(
                organisation_id="Loyalty Angels",
                client_secret="8vA/fjVA83(n05LWh7R4'$3dWmVCU",
                bundle_id="com.bink.wallet",
                email="test@user.mail",
                magic_link=True
            ).get_token()

            It is also possible to generate an expired magic link token for testing purposes
            by passing the additional parameter "expired=True".
            NB: This parameter has no effect on Bearer tokens.
    """

    def __init__(
        self,
        organisation_id: str,
        client_secret: str,
        bundle_id: str,
        email: str = None,
        magic_link: bool = False,
        expired: bool = False,
    ):
        self.bundle_id = bundle_id
        self.organisation_id = organisation_id
        self.secret = client_secret
        self.payload = self._format_payload(email, magic_link, expired)

    def _format_payload(self, email: str, magic_link: bool, expired: bool) -> dict:
        now = arrow.utcnow()
        user = email or "test@binktest.com"
        payload = {"bundle_id": self.bundle_id, "iat": now.timestamp}
        if magic_link:
            payload["email"] = user
            if expired:
                payload["exp"] = now.shift(minutes=-1).timestamp
            else:
                payload["exp"] = now.shift(hours=1).timestamp
        else:
            payload["user_id"] = user
            payload["organisation_id"] = self.organisation_id
            payload["property_id"] = "not currently used for authentication"

        return payload

    def get_token(self) -> str:
        return jwt.encode(self.payload, self.secret, algorithm="HS512").decode("UTF-8")


if __name__ == "__main__":
    token = GenerateJWToken(
        organisation_id="Loyalty Angels",
        client_secret="8vA/fjVA83(n05LWh7R4'$3dWmVCU",
        bundle_id="com.bink.wallet",
        email="test@user.mail",
        magic_link=False,
    ).get_token()
    print(token)
