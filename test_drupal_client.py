import unittest
from unittest.mock import MagicMock, patch
import json
import configparser
from drupal_client import DrupalClient

class TestDrupalClient(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config['Login'] = {
            'login_url': 'http://test.com/login',
            'username': 'testuser',
            'password': 'testpassword',
            'permission_id': 'test_perm',
            'api_url': 'http://test.com/api/{endpoint}/{identifier}/{permission_id}'
        }
        self.config['Station'] = {
            'workstation_id': 'test_station',
            'tool_numerical_id': '123'
        }
        self.client = DrupalClient(self.config)

    @patch('requests.Session.post')
    def test_login_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        self.assertTrue(self.client.login())
        mock_post.assert_called_with(
            'http://test.com/login',
            data={"name": "testuser", "pass": "testpassword", "form_id": "user_login", "op": "Log in"}
        )

    @patch('requests.Session.post')
    def test_login_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        self.assertFalse(self.client.login())

    @patch('requests.Session.get')
    def test_request_access(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        response = self.client.request_access('12345', False)
        self.assertEqual(response.status_code, 200)

        expected_url = "http://test.com/api/serial/12345/test_perm?source=test_station&method=MakerAuth"
        mock_get.assert_called()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], expected_url)

    def test_convert_to_hexadecimal(self):
        # 12345 in hex is 0x3039 -> 3039
        self.assertEqual(DrupalClient.convert_to_hexadecimal('12345', 'decimal'), '3039')
        # if input is already something else or fails int conversion
        self.assertEqual(DrupalClient.convert_to_hexadecimal('ABC', 'decimal'), 'ABC')
        # if not decimal format requested
        self.assertEqual(DrupalClient.convert_to_hexadecimal('12345', 'hexadecimal'), '12345')

if __name__ == '__main__':
    unittest.main()
