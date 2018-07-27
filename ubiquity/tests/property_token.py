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
            "Organisation ID": self.client_id,
            "Bundle ID": self.bundle_id,
            "User ID": email or "test@binktest.com",
            "Email": email or "test@binktest.com",
            "iat": arrow.utcnow().timestamp
        }

    def get_token(self):
        return jwt.encode(self.payload, self.secret, algorithm='HS512').decode('UTF-8')


if __name__ == '__main__':
    bundle = 'com.bink.wallet'
    client = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'
    secret = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"
    print(GenerateJWToken(client, secret, bundle, 'test@delete.mail').get_token())

# usefult one
# eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJPcmdhbmlzYXRpb24gSUQiOiJNS2QzRmZER0JpMUNJVVF3dGFobVBhcDY0bG5lQ2EyUjZHdlZXS2c2ZE5nNHc5Sm5wZCIsIkJ1bmRsZSBJRCI6ImNvbS5iaW5rLndhbGxldCIsIlVzZXIgSUQiOiJ0ZXN0QGJpbmt0ZXN0LmNvbSIsIkVtYWlsIjoidGVzdEBiaW5rdGVzdC5jb20iLCJpYXQiOjE1MzI2OTc5NDV9.uk6vq1BnkGw2pYn5XcJLShyty05yWR5lFA0easjrKBjwneERrLrZjwBf0bz1Fd-u-fnMWN99UrWq8ndmwyvKmg

# eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJPcmdhbmlzYXRpb24gSUQiOiJNS2QzRmZER0JpMUNJVVF3dGFobVBhcDY0bG5lQ2EyUjZHdlZXS2c2ZE5nNHc5Sm5wZCIsIkJ1bmRsZSBJRCI6ImNvbS5iaW5rLndhbGxldCIsIlVzZXIgSUQiOiJ0ZXN0QGRlbGV0ZS5tYWlsIiwiRW1haWwiOiJ0ZXN0QGRlbGV0ZS5tYWlsIiwiaWF0IjoxNTMyNzAyNzAyfQ.ZChGo0-XX-BoIE0IqBkO8a7hE4QczN8fTkEkz_9k7koFIOpdzWlTFfVw6251-KaFzjED75rIahAmVcRwQbUObA