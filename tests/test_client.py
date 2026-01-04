import unittest
from unittest.mock import patch, MagicMock
from issabel_client import IssabelClient

class TestIssabelClient(unittest.TestCase):
    def setUp(self):
        self.client = IssabelClient("192.168.1.100", use_ssl=False)

    @patch('requests.Session.post')
    def test_authenticate_success(self, mock_post):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"access_token": "fake_access", "refresh_token": "fake_refresh"}'
        mock_response.json.return_value = {"access_token": "fake_access", "refresh_token": "fake_refresh"}
        mock_post.return_value = mock_response

        result = self.client.authenticate("admin", "password")
        
        self.assertEqual(result["access_token"], "fake_access")
        self.assertEqual(self.client.access_token, "fake_access")
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer fake_access")

    @patch('requests.Session.request')
    def test_get_resource(self, mock_request):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success", "data": []}'
        mock_response.json.return_value = {"status": "success", "data": []}
        mock_request.return_value = mock_response

        # Set fake token
        self.client.access_token = "fake_access"
        
        result = self.client.get_extensions()
        
        self.assertEqual(result["status"], "success")
        mock_request.assert_called_with(
            method="GET",
            url="http://192.168.1.100/pbxapi/extensions",
            json=None,
            params={},
            headers={"Content-Type": "application/json"},
            verify=False
        )

    @patch('requests.Session.request')
    def test_create_resource(self, mock_request):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        data = {"name": "Test"}
        result = self.client.create_extensions(data)
        
        # Check that reload was added
        expected_data = {"name": "Test", "reload": "true"}
        mock_request.assert_called_with(
            method="POST",
            url="http://192.168.1.100/pbxapi/extensions",
            json=expected_data,
            params=None,
            headers={"Content-Type": "application/json"},
            verify=False
        )

if __name__ == '__main__':
    unittest.main()
