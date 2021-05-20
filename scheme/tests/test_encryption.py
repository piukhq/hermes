from history.utils import GlobalMockAPITestCase
from scheme.encryption import AESCipher
from ubiquity.channel_vault import AESKeyNames


class TestEncryption(GlobalMockAPITestCase):
    def test_encryption(self):
        # Test sample passwords with various non ASCII characters.
        cipher = AESCipher(AESKeyNames.LOCAL_AES_KEY)
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
        cipher = AESCipher(AESKeyNames.LOCAL_AES_KEY)
        original_string = ''
        with self.assertRaises(TypeError):
            cipher.encrypt(original_string)

    def test_decrypt_empty_string(self):
        cipher = AESCipher(AESKeyNames.LOCAL_AES_KEY)
        encrypted_string = ''
        with self.assertRaises(TypeError):
            cipher.decrypt(encrypted_string)
