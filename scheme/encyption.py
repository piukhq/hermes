import base64
import hashlib
from Crypto import Random
from Crypto.Cipher import AES

# TODO : this should become its own library


class AESCipher(object):
    def __init__(self, key):
        self.bs = 32
        self.key = hashlib.sha256(key).digest()

    def encrypt(self, raw):
        if raw == '':
            raise TypeError('Cannot encrypt nothing')
        raw = self._pad(raw.encode('utf-8'))
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        if enc == '':
            raise TypeError('Cannot decrypt nothing')
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        length = self.bs - (len(s) % self.bs)
        return s + bytes([length]) * length

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]
