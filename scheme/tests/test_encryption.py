from django.conf import settings

from history.utils import GlobalMockAPITestCase
from scheme.encyption import AESCipher


class TestEncryption(GlobalMockAPITestCase):
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

    def test_encrypt_empty_string(self):
        cipher = AESCipher(settings.LOCAL_AES_KEY.encode())
        original_string = ''
        with self.assertRaises(TypeError):
            cipher.encrypt(original_string)

    def test_decrypt_empty_string(self):
        cipher = AESCipher(settings.LOCAL_AES_KEY.encode())
        encrypted_string = ''
        with self.assertRaises(TypeError):
            cipher.decrypt(encrypted_string)
