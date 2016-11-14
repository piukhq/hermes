from django.test import TestCase
from scheme.encyption import AESCipher
from django.conf import settings


class TestEncryption(TestCase):
    def test_encryption(self):
        # Test sample passwords with various non ASCII characters.
        cipher = AESCipher(settings.LOCAL_AES_KEY.encode())
        original_string = 'Test£2016'
        encrypted_string = cipher.encrypt(original_string)
        decrypted_string = cipher.decrypt(encrypted_string)
        self.assertEqual(original_string, decrypted_string)

        original_string = 'Testħ2016'
        encrypted_string = cipher.encrypt(original_string)
        decrypted_string = cipher.decrypt(encrypted_string)
        self.assertEqual(original_string, decrypted_string)

        original_string = 'Testµ2016'
        encrypted_string = cipher.encrypt(original_string)
        decrypted_string = cipher.decrypt(encrypted_string)
        self.assertEqual(original_string, decrypted_string)
