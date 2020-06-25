from Crypto.PublicKey import RSA
from shared_config_storage.credentials.encryption import RSACipher

from hermes.channel_vault import get_key


class MockJeffDecryption:
    status_code = 200

    def __init__(self, bundle_id, data):
        key = RSA.import_key(get_key(bundle_id, 'private_key'))
        rsa_cipher = RSACipher()
        self.data = {
            k: rsa_cipher.decrypt(v, rsa_key=key)
            for k, v in data.items()
        }

    @staticmethod
    def raise_for_status():
        return True

    def json(self):
        return self.data


class MockRetrySession:
    def post(self, url, json):
        bundle_id = url.split('/')[-2]
        return MockJeffDecryption(bundle_id, json)
