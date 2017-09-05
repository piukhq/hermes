from scheme.views import CreateMy360AccountsAndLink
from unittest import TestCase
from unittest.mock import patch, MagicMock


class TestMy360(TestCase):

    @patch('requests.get')
    def test_my360_get_schemes_no_schemes(self, request_mock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            'valid': True,
            'schemes': []
        })

        request_mock.return_value = mock_response

        card_number = '012345'
        my_360_schemes = CreateMy360AccountsAndLink.get_my360_schemes(card_number)

        request_mock.assert_called_once_with(
            'https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes'.format(card_number)
        )
        self.assertEqual(my_360_schemes, [])

    @patch('requests.get')
    def test_my360_get_schemes_three_schemes(self, request_mock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            'valid': True,
            'schemes': ['K7yej1', '-fdK4i', 'hewtts']
        })

        request_mock.return_value = mock_response

        card_number = '012345'
        my_360_schemes = CreateMy360AccountsAndLink.get_my360_schemes(card_number)

        request_mock.assert_called_once_with(
            'https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes'.format(card_number)
        )
        self.assertEqual(my_360_schemes, ['cliff-roe-sports', 'the-food-cellar', 'hewetts'])

    @patch('requests.get')
    def test_my360_get_schemes_return_invalid_on_bad_request(self, request_mock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            'valid': False,
            'schemes': []
        })

        request_mock.return_value = mock_response

        card_number = '0123456789101112'
        error_response = CreateMy360AccountsAndLink.get_my360_schemes(card_number)

        request_mock.assert_called_once_with(
            'https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes'.format(card_number)
        )

        self.assertEqual(error_response.data, {'code': 400, 'message': 'Error getting schemes from My360'})
        self.assertEqual(error_response.status_code, 400)

    @patch('requests.get')
    def test_my360_get_schemes_handles_bad_request(self, request_mock):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json = MagicMock(return_value='Not Found')

        request_mock.return_value = mock_response

        card_number = '0123456789101112'
        error_response = CreateMy360AccountsAndLink.get_my360_schemes(card_number)

        request_mock.assert_called_once_with(
            'https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes'.format(card_number)
        )

        self.assertEqual(error_response.data, {'code': 400, 'message': 'Error getting schemes from My360'})
        self.assertEqual(error_response.status_code, 400)
