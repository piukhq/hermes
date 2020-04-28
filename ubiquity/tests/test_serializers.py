import typing as t
from unittest.mock import patch

from Crypto.PublicKey import RSA
from rest_framework.test import APITestCase
from shared_config_storage.credentials.encryption import RSACipher, BLAKE2sHash

from hermes.channel_vault import SecretKeyName, channel_vault
from payment_card.tests.factories import IssuerFactory, PaymentCardFactory
from ubiquity.versioning.v1_2.serializers import (
    PaymentCardTranslationSerializer as PaymentCardTranslationSerializerV1_2
)

private_key = ('-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAA'
               'AAAAAABAAACFwAAAAdzc2gtcn\nNhAAAAAwEAAQAAAgEAsaRcsffAfiNtg90N4nsNai+aebw310s3Ok4OR'
               'W8/SUBMkBhnjxoW\nixdcOj50A8JyadrIKWhxIFKsVX5vJcYTGo7i//c/nwHl08HhtT7pPFzYOM7vaXl+b'
               '/tacQ\n7YZP5VlGtem458J46F9iKGZGQm+9qV+RXGbr+BMCYb9panMJYIPUlDf8HOp0AqBZHXf9b0\n1YT'
               'SnrZaAAVwKuTUwGd/8qs6C9IQxizNic9Kjurg5dsVQwqtmZhB8B92YPWLZ5DRMF5XVc\nmxsU1QdY9LbGT'
               'Pqf7TXcg9mf85aKHSkP6BvqppG5L2ASnx/OQfARMUabgqkaJLfZg6kFu5\nn3hgwmO2GF7zUkqYqVs7RzK'
               '61q8nyh3iM6AUgOPTXh10t63sN0sMF+zDllcJD62ZPLObAj\nS6kbAEVdY1vpy8NereKTrT5W+XAM3VYJr'
               'MwUd3xo3KgnKe8W+lW8Qo2fWYVA898PoH8jdZ\nWJJDYgVB8O0ZCW6+i4uXc03lxDRSkMQpQInbBsvwS3f'
               'fc9iUVJloGsb108pQCH/gwFVR0O\nmXSJjKsTMadrORiLHltrAuWCyZgYeV9Ikwd0FYTp2Aa4v19jQZSRN'
               'iH21PPeOwR2p/9vpk\nxuty8XqYd1kLfJ0rueJsTDYOyxeSzd4MHY/iI895jJ4Diu5/7Vx2E882tLgEgQx'
               'VdI4kFj\ncAAAdIeR8WnHkfFpwAAAAHc3NoLXJzYQAAAgEAsaRcsffAfiNtg90N4nsNai+aebw310s3\nO'
               'k4ORW8/SUBMkBhnjxoWixdcOj50A8JyadrIKWhxIFKsVX5vJcYTGo7i//c/nwHl08HhtT\n7pPFzYOM7va'
               'Xl+b/tacQ7YZP5VlGtem458J46F9iKGZGQm+9qV+RXGbr+BMCYb9panMJYI\nPUlDf8HOp0AqBZHXf9b01'
               'YTSnrZaAAVwKuTUwGd/8qs6C9IQxizNic9Kjurg5dsVQwqtmZ\nhB8B92YPWLZ5DRMF5XVcmxsU1QdY9Lb'
               'GTPqf7TXcg9mf85aKHSkP6BvqppG5L2ASnx/OQf\nARMUabgqkaJLfZg6kFu5n3hgwmO2GF7zUkqYqVs7R'
               'zK61q8nyh3iM6AUgOPTXh10t63sN0\nsMF+zDllcJD62ZPLObAjS6kbAEVdY1vpy8NereKTrT5W+XAM3VY'
               'JrMwUd3xo3KgnKe8W+l\nW8Qo2fWYVA898PoH8jdZWJJDYgVB8O0ZCW6+i4uXc03lxDRSkMQpQInbBsvwS'
               '3ffc9iUVJ\nloGsb108pQCH/gwFVR0OmXSJjKsTMadrORiLHltrAuWCyZgYeV9Ikwd0FYTp2Aa4v19jQZ\n'
               'SRNiH21PPeOwR2p/9vpkxuty8XqYd1kLfJ0rueJsTDYOyxeSzd4MHY/iI895jJ4Diu5/7V\nx2E882tLgE'
               'gQxVdI4kFjcAAAADAQABAAACAQCH+PtK7gzVgGCvcmDSXsYh5VYkoEFN9jDL\n3DtoQoL6mtD/6u45xwpC'
               'ZRsfKfa7efcBt4lGyL7ustleh2ykST0OMxjmPGbiWx2EPP97MD\nBvF9IZiawP3AM/y/GqYGaax2LSPG0q'
               'PKIj1SANCtg7t71vQh1Rj61X0BYeuMzmruJCelTM\nNGwKOlroAmEn6j49iFfXp9dfzMyO/5qf+pAuxgpV'
               'wWKo8Z4NUvXw6k5znq2Ow2c+7cl7q+\nOs3ShLhyexmlPE5jGLZNsyj69qjMh6q5+Yy4kWW9NrMMTMpjD6'
               '8xR00ROrG45ZzbWAkUx6\nEhSp52IOH2ARPph1LwCiZA4MPS5/qf1J47Dg/lAd+GfJz+7tg1wsUTNDaEVS'
               'hNpJRuKqbj\n3ECFLcM1knSZcAqj1D8+meBI0Fw4oe1tfH6PesYmTPlCgpNb/ra94T1acrWm1T0wopWA6V'
               '\nY6XJ9va+mYXqM5Ly+LUG+lXZSo4Hhyys8HQ7FfNcepEKU9H1MhcR5w+oxPutkeyE3+28T9\nE5FoDI2p'
               'eBhbyGGMklbB9uuAeCTYsK0COkDWZt+gYKIv2PHXVTJxcd2TbGsXG301GfRueT\nT9JwyCheI0W7l30doM'
               'YxpCNVlknHNJ790GBERgKvghY9jc1E1T1IQG+elfgRbUiI+uM7Yg\nrikwMaRN7/oSRFI+b5oQAAAQBtmh'
               '+H734PeSEynYqipJ8F+V0+r20Hcf9KFP/HSjzhPPNH\nbXxW0wKKCYk4lNG5nV2TVaJdgkzQxuVr6/foQU'
               'vITzsEIerIzeQec8xtPS2CnBvi8xyhZu\nUU/qLJISAymEfbqOn4Hu+Bej+TVWZcAPzQeHEXQh3vvY5gAx'
               'gxiAzaJI0G5+8jmU7OzGpE\nIipYmOPavSnJZN6jl10DEfwUQxST66QN6G8vSDpmCPXpujBgm8hgNBw9yJ'
               'Kq0zA6ZMpIdr\n7WJJ8m3xVyM0AVLbiWrFEOxQUvbyZviVmg3aeOmktYci7S9AhhTVwS4iTT7BGq5gdxZ4'
               'Xt\nh2a8y8Cb9n0lftjNAAABAQDimmtzuW9DDrNulg9If3nYsRthemCE/mtEiR3dby85rnxQsY\nXYLOgx'
               '11mrGNG3xTrWq4MxxJGjHeRyg65hLfdTfoQXI5FSv8IbT4GptOrL0rHHZp15ARE5\nh+gZDuiBwxt7+/8K'
               '8EouhCeWzWDr2JfvqcrBl9UbNxrma+FBpVCxHYLVKzfGzwE5ZFjIxX\nWSz1YnVlKJDlY+NWilW1Ln2B/3'
               '94j+J7rqAGX9wlZ7r0TdEvqPK3o00TE7G8yA9dIFHuje\nyEt5p63tBDg88jpg6OJ0wTmMVg7rsvdsUC4A'
               'iVp7aG4d8c/u1v3TyWiM6VGQ4F8OGpExvg\nsRkDcQXz81l37VAAABAQDIr+xTUPHLqQ30vPeeN89UboTq'
               'pTUnPk54bHpaF9EhtysvMWqL\n8BWWbO/I+Sp104FG07fL3DrfFqjVioZ5nn1dEls0woBoEjlZ3gBV9xqu'
               'Vy2KHaV694o0o/\nBWwVW0hbgITSntu4xvo3ajQG40tdckZcGgOEVrosC9sJ00UczxljSH3uI1evWxESof'
               'C1zK\nhADENYgqNVJY44tcrF77j0tOQbtamyl6BLDA/9xrotSECGVH0ekWEh9dhXS3CxSgiJLUs4\nmoAh'
               '0wW/oHwHlCZQVHCxU6B56Qt/SApfWk97GLMBi9tCDawHuBdivBcNM4xtGpog33HeuQ\nZtWRYsDZBz7bAA'
               'AADXRlc3RAYmluay5jb20BAgMEBQ==\n-----END OPENSSH PRIVATE KEY-----')

mock_secrets = {
    'bundle_secrets': {
        'com.barclays.test': {
            'private_key': private_key,
            'public_key': (
                'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCxpFyx98B+I22D3Q3iew1qL5p5vDfXSzc6Tg5Fbz9JQEy'
                'QGGePGhaLF1w6PnQDwnJp2sgpaHEgUqxVfm8lxhMajuL/9z+fAeXTweG1Puk8XNg4zu9peX5v+1pxDthk/l'
                'WUa16bjnwnjoX2IoZkZCb72pX5FcZuv4EwJhv2lqcwlgg9SUN/wc6nQCoFkdd/1vTVhNKetloABXAq5NTAZ'
                '3/yqzoL0hDGLM2Jz0qO6uDl2xVDCq2ZmEHwH3Zg9YtnkNEwXldVybGxTVB1j0tsZM+p/tNdyD2Z/zloodKQ'
                '/oG+qmkbkvYBKfH85B8BExRpuCqRokt9mDqQW7mfeGDCY7YYXvNSSpipWztHMrrWryfKHeIzoBSA49NeHXS'
                '3rew3SwwX7MOWVwkPrZk8s5sCNLqRsARV1jW+nLw16t4pOtPlb5cAzdVgmszBR3fGjcqCcp7xb6VbxCjZ9Z'
                'hUDz3w+gfyN1lYkkNiBUHw7RkJbr6Li5dzTeXENFKQxClAidsGy/BLd99z2JRUmWgaxvXTylAIf+DAVVHQ6'
                'ZdImMqxMxp2s5GIseW2sC5YLJmBh5X0iTB3QVhOnYBri/X2NBlJE2IfbU8947BHan/2+mTG63Lxeph3WQt8'
                'nSu54mxMNg7LF5LN3gwdj+Ijz3mMngOK7n/tXHYTzza0uASBDFV0jiQWNw== test@bink.com'),
            'rsa_key': RSA.import_key(private_key)
        }
    },
    'secret_keys': {
        SecretKeyName.PCARD_HASH_SECRET: 'secret'
    }
}


class TestSerializersV1_2(APITestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle_id = 'com.barclays.test'
        cls.rsa = RSACipher()
        cls.pub_key = mock_secrets["bundle_secrets"][cls.bundle_id]['public_key']

        IssuerFactory(name='Barclays')
        PaymentCardFactory(slug='mastercard')

    @classmethod
    def tearDownClass(cls):
        pass

    @patch.object(channel_vault, 'all_secrets', mock_secrets)
    def test_payment_card_translation_serializer(self):
        serializer = PaymentCardTranslationSerializerV1_2
        hash1 = 'hash1'
        data = {
            'fingerprint': 'testfingerprint00068',
            'token': 'testtoken00068',
            'name_on_card': 'Test Card',
            'hash': self.rsa.encrypt(hash1, pub_key=self.pub_key),
            'first_six_digits': self.rsa.encrypt('555555', pub_key=self.pub_key),
            'last_four_digits': self.rsa.encrypt('4444', pub_key=self.pub_key),
            'month': self.rsa.encrypt(12, pub_key=self.pub_key),
            'year': self.rsa.encrypt(2025, pub_key=self.pub_key)
        }

        hash2 = BLAKE2sHash().new(
            obj=hash1,
            key=t.cast(str, mock_secrets['secret_keys'][SecretKeyName.PCARD_HASH_SECRET])
        )

        expected_data = {
            'fingerprint': 'testfingerprint00068',
            'token': 'testtoken00068',
            'name_on_card': 'Test Card',
            'hash': hash2,
            'pan_start': '555555',
            'pan_end': '4444',
            'expiry_month': 12,
            'expiry_year': 2025
        }

        serialized_data = serializer(data, context={'bundle_id': self.bundle_id}).data

        self.assertTrue(expected_data.items() < serialized_data.items())
