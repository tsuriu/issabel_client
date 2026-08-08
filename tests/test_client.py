import unittest
from unittest.mock import patch, MagicMock
from issabel_client import IssabelClient


class TestIssabelClient(unittest.TestCase):

    def setUp(self):
        self.client = IssabelClient("192.168.1.100", use_ssl=False, timeout=10)
        self.client.access_token = "fake_access"
        self.client.refresh_token = "fake_refresh"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @patch("requests.Session.post")
    def test_authenticate_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"access_token": "fake_access", "refresh_token": "fake_refresh"}'
        mock_response.json.return_value = {"access_token": "fake_access", "refresh_token": "fake_refresh"}
        mock_post.return_value = mock_response

        result = self.client.authenticate("admin", "password")

        self.assertEqual(result["access_token"], "fake_access")
        self.assertEqual(self.client.access_token, "fake_access")
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer fake_access")

    @patch("requests.Session.post")
    def test_authenticate_403_raises_valueerror(self, mock_post):
        """HTTP 403 must raise ValueError with a friendly message."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            self.client.authenticate("admin", "wrong_password")

        self.assertIn("invalid credentials", str(ctx.exception))

    # ------------------------------------------------------------------
    # GET resource
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_get_resource(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success", "data": []}'
        mock_response.json.return_value = {"status": "success", "data": []}
        mock_request.return_value = mock_response

        result = self.client.get_extensions()

        self.assertEqual(result["status"], "success")
        mock_request.assert_called_once_with(
            method="GET",
            url="http://192.168.1.100/pbxapi/extensions",
            json=None,
            params=None,
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10,
        )

    # ------------------------------------------------------------------
    # reload=True (default)
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_create_resource_reload_true(self, mock_request):
        """Default create should include reload=true in the payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        self.client.create_extensions({"name": "Test"})

        expected_data = {"name": "Test", "reload": "true"}
        mock_request.assert_called_once_with(
            method="POST",
            url="http://192.168.1.100/pbxapi/extensions",
            json=expected_data,
            params=None,
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10,
        )

    # ------------------------------------------------------------------
    # Bug fix §1 — reload=False
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_create_resource_reload_false(self, mock_request):
        """create_resource with reload=False must include reload='false' in payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        self.client.create_extensions({"name": "Test"}, reload=False)

        call_kwargs = mock_request.call_args
        sent_payload = call_kwargs.kwargs["json"]
        self.assertEqual(sent_payload["reload"], "false", "reload=False must propagate as 'false' string")

    @patch("requests.Session.request")
    def test_delete_resource_reload_false(self, mock_request):
        """delete_resource with reload=False must include reload='false' in DELETE body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        self.client.delete_extensions("2000", reload=False)

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["method"], "DELETE")
        sent_payload = call_kwargs.kwargs["json"]
        self.assertIsNotNone(sent_payload, "DELETE must include a JSON body when reload is specified")
        self.assertEqual(sent_payload["reload"], "false")

    # ------------------------------------------------------------------
    # Token renewal
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    @patch("requests.Session.get")
    def test_token_renewal_on_401(self, mock_get, mock_request):
        """On HTTP 401, the client must renew the token and retry."""
        # First call returns 401, second succeeds.
        response_401 = MagicMock()
        response_401.status_code = 401
        response_401.content = b""

        response_ok = MagicMock()
        response_ok.status_code = 200
        response_ok.content = b'{"data": "ok"}'
        response_ok.json.return_value = {"data": "ok"}

        mock_request.side_effect = [response_401, response_ok]

        # renew_token uses session.get internally
        renew_response = MagicMock()
        renew_response.status_code = 200
        renew_response.content = (
            b'{"status": "authorized", "access_token": "new_token", "refresh_token": "new_refresh"}'
        )
        renew_response.json.return_value = {
            "status": "authorized",
            "access_token": "new_token",
            "refresh_token": "new_refresh",
        }
        mock_get.return_value = renew_response

        result = self.client.get_extensions()

        self.assertEqual(result["data"], "ok")
        self.assertEqual(self.client.access_token, "new_token")

    @patch("requests.Session.request")
    @patch("requests.Session.get")
    def test_token_renewal_legacy_expired(self, mock_get, mock_request):
        """200 response with status=expired must trigger token renewal and retry."""
        response_expired = MagicMock()
        response_expired.status_code = 200
        response_expired.content = b'{"status": "expired"}'
        response_expired.json.return_value = {"status": "expired"}

        response_ok = MagicMock()
        response_ok.status_code = 200
        response_ok.content = b'{"data": "renewed"}'
        response_ok.json.return_value = {"data": "renewed"}

        mock_request.side_effect = [response_expired, response_ok]

        renew_response = MagicMock()
        renew_response.status_code = 200
        renew_response.content = b'{"status": "authorized", "access_token": "new_tok", "refresh_token": "new_ref"}'
        renew_response.json.return_value = {
            "status": "authorized",
            "access_token": "new_tok",
            "refresh_token": "new_ref",
        }
        mock_get.return_value = renew_response

        result = self.client.get_extensions()
        self.assertEqual(result["data"], "renewed")

    # ------------------------------------------------------------------
    # Search URL
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_search_builds_correct_url(self, mock_request):
        """search() must call /{resource}/search/{term} as the URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": []}'
        mock_response.json.return_value = {"data": []}
        mock_request.return_value = mock_response

        self.client.search("extensions", "john", fields=["name", "extension"])

        call_kwargs = mock_request.call_args
        self.assertIn("/extensions/search/john", call_kwargs.kwargs["url"])
        self.assertEqual(call_kwargs.kwargs["params"]["fields"], "name,extension")

    # ------------------------------------------------------------------
    # Delete multiple IDs
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_delete_multiple_ids(self, mock_request):
        """Passing a list of IDs must join them with commas in the URL path."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        self.client.delete_resource("ivr", ["1", "2", "3"])

        call_kwargs = mock_request.call_args
        self.assertIn("ivr/1,2,3", call_kwargs.kwargs["url"])

    # ------------------------------------------------------------------
    # Read-only guard (§2.2)
    # ------------------------------------------------------------------

    def test_readonly_resource_create_raises(self):
        """create_modules() must raise NotImplementedError client-side."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.client.create_modules({"name": "test"})
        self.assertIn("read-only", str(ctx.exception))

    def test_readonly_resource_delete_raises(self):
        """delete_featurecodes() must raise NotImplementedError client-side."""
        with self.assertRaises(NotImplementedError):
            self.client.delete_featurecodes("*97")

    def test_get_put_only_resource_create_raises(self):
        """create_classofserviceadmin() must raise NotImplementedError (GET+PUT only)."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.client.create_classofserviceadmin({"context": "test"})
        self.assertIn("POST", str(ctx.exception))

    # ------------------------------------------------------------------
    # Manager proxy (§2.1)
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_manager_originate(self, mock_request):
        """manager.originate() must send GET to manager/originate with query params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"result": "Originate successful"}'
        mock_response.json.return_value = {"result": "Originate successful"}
        mock_request.return_value = mock_response

        self.client.manager.originate(
            channel="SIP/1001", extension="1002", context="from-internal", priority=1
        )

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["method"], "GET")
        self.assertIn("manager/originate", call_kwargs.kwargs["url"])
        params = call_kwargs.kwargs["params"]
        self.assertEqual(params["channel"], "SIP/1001")
        self.assertEqual(params["extension"], "1002")

    @patch("requests.Session.request")
    def test_manager_dbget(self, mock_request):
        """manager.dbget() must send GET to manager/dbget with family and key params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"value": "test_value"}'
        mock_response.json.return_value = {"value": "test_value"}
        mock_request.return_value = mock_response

        self.client.manager.dbget(family="MyFamily", key="MyKey")

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["method"], "GET")
        self.assertIn("manager/dbget", call_kwargs.kwargs["url"])
        params = call_kwargs.kwargs["params"]
        self.assertEqual(params["family"], "MyFamily")
        self.assertEqual(params["key"], "MyKey")

    # ------------------------------------------------------------------
    # Timeout (§3.1)
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_timeout_propagated(self, mock_request):
        """All requests must include the timeout configured at __init__."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"ok": true}'
        mock_response.json.return_value = {"ok": True}
        mock_request.return_value = mock_response

        client = IssabelClient("192.168.1.100", use_ssl=False, timeout=42)
        client.access_token = "tok"
        client.get_extensions()

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["timeout"], 42)

    # ------------------------------------------------------------------
    # Batch context (user requirement)
    # ------------------------------------------------------------------

    @patch("requests.Session.request")
    def test_batch_context_no_individual_reloads(self, mock_request):
        """Inside client.batch(), every write operation must have reload='false'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        with self.client.batch():
            for ext_num in range(1001, 1004):
                self.client.create_extensions({
                    "extension": str(ext_num),
                    "name": f"User {ext_num}",
                    "secret": "s3cr3t",
                })

        # The last call is the automatic reload via manager.reload() (GET) — skip it.
        # All POST calls should have reload=false.
        post_calls = [
            c for c in mock_request.call_args_list
            if c.kwargs.get("method") == "POST"
        ]
        self.assertEqual(len(post_calls), 3, "Expected exactly 3 POST calls")
        for c in post_calls:
            payload = c.kwargs["json"]
            self.assertEqual(
                payload["reload"], "false",
                f"Expected reload='false' in POST payload, got: {payload}"
            )

    @patch("requests.Session.request")
    def test_batch_context_fires_single_reload_at_end(self, mock_request):
        """On exit from batch(), exactly one GET to manager/reload must be fired."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "success"}'
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        with self.client.batch():
            self.client.create_extensions({"extension": "1001", "name": "User", "secret": "s"})
            self.client.create_extensions({"extension": "1002", "name": "User", "secret": "s"})

        reload_calls = [
            c for c in mock_request.call_args_list
            if c.kwargs.get("method") == "GET" and "manager/reload" in c.kwargs.get("url", "")
        ]
        self.assertEqual(len(reload_calls), 1, "Expected exactly one manager/reload GET after batch exit")


if __name__ == "__main__":
    unittest.main()
