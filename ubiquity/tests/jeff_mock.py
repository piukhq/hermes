import binascii

from Crypto.PublicKey import RSA
from requests import HTTPError
from shared_config_storage.credentials.encryption import RSACipher


class MockJeffDecryption:
    status_code = 200

    def __init__(self, bundle_id, data, get_key_func):
        key = RSA.import_key(get_key_func(bundle_id, 'private_key'))
        rsa_cipher = RSACipher()
        try:
            self.data = {
                k: rsa_cipher.decrypt(v, rsa_key=key)
                for k, v in data.items()
            }
        except binascii.Error:
            self.data = {}
            self.status_code = 400

    def raise_for_status(self):
        if self.status_code is not 200:
            raise HTTPError

    def json(self):
        return self.data


class MockRetrySession:
    def __init__(self, get_key_func=None):
        if get_key_func:
            self.get_key_func = get_key_func
        else:
            from hermes.channel_vault import get_key
            self.get_key_func = get_key

    def post(self, url, json):
        bundle_id = url.split('/')[-2]
        return MockJeffDecryption(bundle_id, json, self.get_key_func)
