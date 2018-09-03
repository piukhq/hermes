import arrow
import jwt


class GenerateJWToken:
    payload = {}

    def __init__(self, organisation_id, client_secret, bundle_id, email=None):
        self.bundle_id = bundle_id
        self.organisation_id = organisation_id
        self.secret = client_secret
        self._format_payload(email)

    def _format_payload(self, email):
        self.payload = {
            "Organisation ID": self.organisation_id,
            "Bundle ID": self.bundle_id,
            "User ID": email or "test@binktest.com",
            "Property ID": 'not currently used for authentication',
            "iat": arrow.utcnow().timestamp
        }

    def get_token(self):
        return jwt.encode(self.payload, self.secret, algorithm='HS512').decode('UTF-8')


if __name__ == '__main__':
    bundle = 'com.bink.wallet'
    organisation = 'Loyalty Angels'
    secret = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"
    print(GenerateJWToken(organisation, secret, bundle, 'test@delete.mail').get_token())
