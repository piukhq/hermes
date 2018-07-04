import arrow
import jwt


class GenerateJWToken:
    payload = {}

    def __init__(self, client_id, secret, bundle_id, email=None):
        self.bundle_id = bundle_id
        self.client_id = client_id
        self.secret = secret
        self._format_payload(email)

    def _format_payload(self, email):
        self.payload = {
            "Organization ID": self.client_id,
            "Bundle ID": self.bundle_id,
            "User ID": email or "test@binktest.com",
            "Email": email or "test@binktest.com",
            "iat": arrow.utcnow().timestamp
        }

    def get_token(self):
        return jwt.encode(self.payload, self.secret, algorithm='HS512')


if __name__ == '__main__':
    bundle = 'com.bink.wallet'
    client = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'
    secret = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"
    print(GenerateJWToken(client, secret, bundle).get_token())
