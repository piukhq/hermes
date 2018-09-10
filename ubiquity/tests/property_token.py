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
            "organisation_id": self.organisation_id,
            "bundle_id": self.bundle_id,
            "user_id": email or "test@binktest.com",
            "property_id": 'not currently used for authentication',
            "iat": arrow.utcnow().timestamp
        }

    def get_token(self):
        return jwt.encode(self.payload, self.secret, algorithm='HS512').decode('UTF-8')


if __name__ == '__main__':
    bundle = 'com.barclays.test'
    organisation = 'Barclays'
    secret = "R8aLVYe10vbidYTXqdinXfLOeX00uYUUuzEmAfQsHUqQicTb0L"
    print(GenerateJWToken(organisation, secret, bundle, 'test@delete.mail').get_token())
