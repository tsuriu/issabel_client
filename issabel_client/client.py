import requests
import json
import threading
import urllib3
from urllib.parse import urljoin
from typing import Optional, Any, Dict, List, Union

# Disable insecure request warnings for self-signed certificates (common in PBX environments)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__version__ = "0.2.0"


class AuthenticationError(Exception):
    """Raised when authentication or token renewal fails."""
    pass


# Resources that only support GET/SEARCH — any write attempt is rejected server-side (405).
READ_ONLY_RESOURCES: frozenset = frozenset({
    "featurecodes",
    "modules",
    "systemrecordings",
    "allextensions",
    "alldestinations",
})

# Resources that support GET and PUT only — POST and DELETE are not available.
GET_PUT_ONLY_RESOURCES: frozenset = frozenset({
    "classofserviceadmin",
    "routecongestionmessages",
})


class BatchContext:
    """
    Context manager returned by ``IssabelClient.batch()``.

    While active, all write operations (POST, PUT, DELETE) are sent with
    ``reload=false``, preventing individual Asterisk reloads on every call.
    On exit, a single ``manager/reload`` is dispatched to apply all pending
    changes at once — regardless of whether any exception was raised.

    Usage::

        with client.batch():
            for ext in range(1001, 1100):
                client.create_extensions({"extension": str(ext), "name": f"User {ext}", "secret": "s3cr3t"})
        # One reload fired here automatically.
    """

    def __init__(self, client: "IssabelClient") -> None:
        self._client = client

    def __enter__(self) -> "BatchContext":
        self._client._local.batch_mode = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._client._local.batch_mode = False
        # Always attempt the reload — even if an exception occurred — so that
        # any partial changes already sent to the server are applied.
        try:
            self._client.manager.reload()
        except Exception:
            pass  # Reload failure should not shadow the original exception.
        return None  # Never suppress exceptions.


class ManagerProxy:
    """
    Proxy for the Asterisk Manager Interface (AMI) wrapper endpoints at
    ``/pbxapi/manager/{action}``.

    All methods accept keyword arguments that are forwarded as query
    parameters on GET requests or as JSON body on POST/DELETE requests.

    Accessible via ``client.manager``::

        client.manager.originate(channel="SIP/1001", extension="1002", context="from-internal", priority=1)
        client.manager.queuestatus(queue="support")
        client.manager.dbget(family="MyFamily", key="MyKey")
    """

    def __init__(self, client: "IssabelClient") -> None:
        self._client = client

    def _call(self, action: str, method: str, **kwargs: Any) -> Dict[str, Any]:
        url = urljoin(self._client.base_url, f"manager/{action}")
        params = kwargs if method == "GET" else None
        body = kwargs if method in ("POST", "DELETE") else None

        headers = {"Content-Type": "application/json"}
        try:
            response = self._client.session.request(
                method=method,
                url=url,
                json=body,
                params=params,
                headers=headers,
                verify=self._client.verify_ssl,
                timeout=self._client.timeout,
            )
            if response.status_code == 401:
                self._client.renew_token()
                response = self._client.session.request(
                    method=method,
                    url=url,
                    json=body,
                    params=params,
                    headers=headers,
                    verify=self._client.verify_ssl,
                    timeout=self._client.timeout,
                )
            response.raise_for_status()
            return self._client._safe_json_parse(response) or {}
        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "response": getattr(e.response, "text", "")}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            return {"error": f"Network error calling manager/{action}: {e}"}

    # --- AMI action methods ------------------------------------------------

    def queuestatus(self, **kwargs: Any) -> Dict[str, Any]:
        """Return the status of a specific queue or all queues."""
        return self._call("queuestatus", "GET", **kwargs)

    def status(self, **kwargs: Any) -> Dict[str, Any]:
        """Return the status of an active channel."""
        return self._call("status", "GET", **kwargs)

    def extensionstate(self, **kwargs: Any) -> Dict[str, Any]:
        """Return the current registration/usage state of an extension."""
        return self._call("extensionstate", "GET", **kwargs)

    def dbget(self, family: str, key: str, **kwargs: Any) -> Dict[str, Any]:
        """Read a specific key from the AstDB."""
        return self._call("dbget", "GET", family=family, key=key, **kwargs)

    def dbput(self, family: str, key: str, value: str, **kwargs: Any) -> Dict[str, Any]:
        """Insert or update a key/value pair in the AstDB."""
        return self._call("dbput", "POST", family=family, key=key, value=value, **kwargs)

    def dbdel(self, family: str, key: str, **kwargs: Any) -> Dict[str, Any]:
        """Remove a specific key from the AstDB."""
        return self._call("dbdel", "DELETE", family=family, key=key, **kwargs)

    def dbdeltree(self, family: str, **kwargs: Any) -> Dict[str, Any]:
        """Delete an entire AstDB family tree."""
        return self._call("dbdeltree", "GET", family=family, **kwargs)

    def dbshow(self, family: str, **kwargs: Any) -> Dict[str, Any]:
        """List all keys/values in an AstDB family."""
        return self._call("dbshow", "GET", family=family, **kwargs)

    def queueadd(self, **kwargs: Any) -> Dict[str, Any]:
        """Dynamically add an agent to a queue."""
        return self._call("queueadd", "GET", **kwargs)

    def queueremove(self, **kwargs: Any) -> Dict[str, Any]:
        """Remove an agent from a queue."""
        return self._call("queueremove", "GET", **kwargs)

    def queuepause(self, **kwargs: Any) -> Dict[str, Any]:
        """Pause an agent in a queue."""
        return self._call("queuepause", "GET", **kwargs)

    def queueunpause(self, **kwargs: Any) -> Dict[str, Any]:
        """Unpause an agent in a queue."""
        return self._call("queueunpause", "GET", **kwargs)

    def queuelog(self, **kwargs: Any) -> Dict[str, Any]:
        """Add a custom log entry to the queue log."""
        return self._call("queuelog", "GET", **kwargs)

    def reload(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute a full Asterisk reload (``core reload``)."""
        return self._call("reload", "GET", **kwargs)

    def hangup(self, channel: str, **kwargs: Any) -> Dict[str, Any]:
        """Hang up an active call on a channel."""
        return self._call("hangup", "GET", channel=channel, **kwargs)

    def getvar(self, channel: str, variable: str, **kwargs: Any) -> Dict[str, Any]:
        """Return the value of a channel variable in Asterisk."""
        return self._call("getvar", "GET", channel=channel, variable=variable, **kwargs)

    def userevent(self, event: str, **kwargs: Any) -> Dict[str, Any]:
        """Fire a custom user event on the AMI."""
        return self._call("userevent", "GET", event=event, **kwargs)

    def originate(self, channel: str, extension: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Originate a new call programmatically.

        :param channel: Originating channel (e.g. ``SIP/1001``).
        :param extension: Destination extension number.
        :param kwargs: Additional AMI originate parameters (``context``,
            ``priority``, ``timeout``, ``callerid``, etc.).
        """
        return self._call("originate", "GET", channel=channel, extension=extension, **kwargs)


class IssabelClient:
    """
    Python Client for Issabel PBX API v0.2.0.

    Provides a dynamic interface to interact with all resources available in
    the Issabel PBX API, plus explicit helpers for the Asterisk Manager
    Interface (AMI) wrapper, batch provisioning, and file uploads.

    Dynamic CRUD methods (via ``__getattr__``)::

        client.get_extensions()
        client.create_extensions(data, reload=True)
        client.update_extensions(ext_id, data, reload=True)
        client.delete_extensions(ext_id, reload=True)

    Batch provisioning (single reload at the end)::

        with client.batch():
            for ext in range(1001, 1100):
                client.create_extensions({...})

    AMI wrapper::

        client.manager.originate(channel="SIP/1001", extension="1002", context="from-internal", priority=1)
        client.manager.reload()
    """

    def __init__(
        self,
        base_url: str,
        use_ssl: bool = True,
        verify_ssl: bool = False,
        timeout: float = 30,
    ) -> None:
        """
        Initialize the Issabel PBX API Client.

        :param base_url: The base URL or IP of the Issabel server.
        :param use_ssl: Whether to use HTTPS (default ``True``).
        :param verify_ssl: Whether to verify SSL certificates (default ``False``).
        :param timeout: Request timeout in seconds (default ``30``).
        """
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{base_url.rstrip('/')}/pbxapi/"
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session = requests.Session()
        self.manager = ManagerProxy(self)
        # Thread-local storage for batch mode flag (thread-safe).
        self._local = threading.local()

    # ------------------------------------------------------------------
    # Context manager — closes the underlying requests.Session on exit.
    # ------------------------------------------------------------------

    def __enter__(self) -> "IssabelClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.session.close()

    # ------------------------------------------------------------------
    # Batch context
    # ------------------------------------------------------------------

    def batch(self) -> BatchContext:
        """
        Return a context manager that batches write operations.

        While the block is active, all POST/PUT/DELETE calls are sent with
        ``reload=false``. On exit, a single ``manager/reload`` is fired
        automatically so that all pending changes are applied to Asterisk
        in one pass.

        Example::

            with client.batch():
                for ext in range(1001, 1100):
                    client.create_extensions({
                        "extension": str(ext),
                        "name": f"User {ext}",
                        "secret": "s3cr3t",
                    })
            # One reload here — Asterisk updated a single time.
        """
        return BatchContext(self)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_json_parse(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON from a response.

        :param response: The requests ``Response`` object.
        :return: Parsed dictionary, or ``None`` if the response body is empty.
        """
        if not response.content:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return {"error": "Invalid JSON response", "content": response.text}

    @property
    def _batch_mode(self) -> bool:
        """Return ``True`` when the current thread is inside a ``batch()`` block."""
        return getattr(self._local, "batch_mode", False)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with the PBX API and retrieve access tokens.

        :param username: PBX API username.
        :param password: PBX API password.
        :return: Authentication result containing ``access_token`` and
            ``refresh_token``.
        :raises ValueError: If credentials are invalid (HTTP 403) or the
            server returns a non-JSON response.
        """
        url = urljoin(self.base_url, "authenticate")
        data = {"user": username, "password": password}
        try:
            response = self.session.post(url, data=data, verify=self.verify_ssl, timeout=self.timeout)
            if response.status_code == 403:
                raise ValueError("Authentication failed: invalid credentials")
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ValueError(f"Authentication failed: {e}") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ValueError(f"Authentication failed: network error — {e}") from e

        result = self._safe_json_parse(response)
        if result and "error" in result:
            raise ValueError(
                f"Authentication failed: Server returned non-JSON response. "
                f"Content: {result.get('content', '')[:200]}"
            )

        self.access_token = result.get("access_token") if result else None
        self.refresh_token = result.get("refresh_token") if result else None

        if self.access_token:
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        return result or {}

    def check_auth_status(self) -> Dict[str, Any]:
        """
        Check the current session state without re-authenticating.

        Sends ``GET /pbxapi/authenticate``.

        :return: Current token info or ``{"status": "unauthorized"}``.
        """
        url = urljoin(self.base_url, "authenticate")
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
            return self._safe_json_parse(response) or {}
        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "response": getattr(e.response, "text", "")}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            return {"error": f"Network error checking auth status: {e}"}

    def renew_token(self) -> Dict[str, Any]:
        """
        Renew the access token using the refresh token.

        :return: Renewal result with new tokens.
        :raises ValueError: If tokens are not available.
        :raises AuthenticationError: If the renewal request fails (expired
            refresh token, network issue, etc.).
        """
        if not self.refresh_token or not self.access_token:
            raise ValueError("No refresh token or access token available. Authenticate first.")

        url = urljoin(
            self.base_url,
            f"authenticate/renewtoken?refresh_token={self.refresh_token}&access_token={self.access_token}",
        )
        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AuthenticationError(
                f"Token renewal failed (HTTP {e.response.status_code}). "
                "Please re-authenticate."
            ) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise AuthenticationError(f"Token renewal failed: network error — {e}") from e

        result = self._safe_json_parse(response)
        if result and result.get("status") == "authorized":
            self.access_token = result.get("access_token")
            self.refresh_token = result.get("refresh_token")
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        return result or {}

    # ------------------------------------------------------------------
    # Core request dispatcher
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        resource: str,
        path_id: Optional[Union[str, int]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        reload: bool = True,
    ) -> Dict[str, Any]:
        """
        Internal helper for making API requests.

        :param method: HTTP method (``GET``, ``POST``, ``PUT``, ``DELETE``).
        :param resource: API resource name (e.g. ``extensions``).
        :param path_id: Optional resource ID appended to the URL path.
        :param data: JSON payload for POST/PUT/DELETE requests.
        :param params: Query parameters for GET requests.
        :param reload: Whether to trigger a config reload after the operation.
            Ignored when inside a ``client.batch()`` block (always ``False``
            while batching).
        :return: Parsed JSON response dictionary.
        """
        path = f"{resource}/{path_id}" if path_id else resource
        url = urljoin(self.base_url, path)

        # Inside a batch block, force reload off regardless of the caller's intent.
        effective_reload = False if self._batch_mode else reload

        # Inject the reload flag for all write methods.
        # Use setdefault so that an explicit "reload" key already present in
        # `data` (e.g. passed directly by the caller) is never overwritten.
        if method in ("POST", "PUT", "DELETE"):
            if data is None:
                data = {}
            data.setdefault("reload", "true" if effective_reload else "false")

        headers = {"Content-Type": "application/json"}

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )

            # Auto-renew token if expired (HTTP 401).
            if response.status_code == 401:
                self.renew_token()
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                )

            # Check for expired token signalled in a 200 body (legacy behavior).
            if response.status_code == 200:
                result = self._safe_json_parse(response)
                if result and result.get("status") == "expired":
                    self.renew_token()
                    response = self.session.request(
                        method=method,
                        url=url,
                        json=data,
                        params=params,
                        headers=headers,
                        verify=self.verify_ssl,
                        timeout=self.timeout,
                    )

            response.raise_for_status()
            return self._safe_json_parse(response) or {}

        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "response": getattr(e.response, "text", "")}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            return {"error": f"Network error on {method} {url}: {e}"}

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        resource: str,
        term: str,
        fields: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Search for a term within a resource.

        :param resource: The resource to search (e.g. ``extensions``).
        :param term: The search term.
        :param fields: Optional field(s) to include in the response.
        :return: Search results.
        """
        params: Optional[Dict[str, Any]] = None
        if fields:
            params = {"fields": fields if isinstance(fields, str) else ",".join(fields)}
        return self._request("GET", f"{resource}/search/{term}", params=params)

    # ------------------------------------------------------------------
    # Generic CRUD methods
    # ------------------------------------------------------------------

    def get_resource(
        self,
        resource: str,
        resource_id: Optional[Union[str, int]] = None,
        fields: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Get one or all records for a resource."""
        params: Optional[Dict[str, Any]] = None
        if fields:
            params = {"fields": fields if isinstance(fields, str) else ",".join(fields)}
        return self._request("GET", resource, path_id=resource_id, params=params)

    def create_resource(
        self,
        resource: str,
        data: Dict[str, Any],
        reload: bool = True,
    ) -> Dict[str, Any]:
        """Create a new record for a resource."""
        return self._request("POST", resource, data=data, reload=reload)

    def update_resource(
        self,
        resource: str,
        resource_id: Union[str, int],
        data: Dict[str, Any],
        reload: bool = True,
    ) -> Dict[str, Any]:
        """Update an existing record for a resource."""
        return self._request("PUT", resource, path_id=resource_id, data=data, reload=reload)

    def delete_resource(
        self,
        resource: str,
        resource_id: Union[str, int, List[Union[str, int]]],
        reload: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete one or more records for a resource.

        :param resource_id: A single ID or a list of IDs. Multiple IDs are
            joined with commas in the URL path (e.g. ``/ivr/1,2,3``).
        """
        if isinstance(resource_id, list):
            resource_id = ",".join(map(str, resource_id))
        return self._request("DELETE", resource, path_id=resource_id, reload=reload)

    # ------------------------------------------------------------------
    # File upload (musiconhold)
    # ------------------------------------------------------------------

    def upload_moh_file(
        self,
        category: str,
        file_path: str,
        reload: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload an audio file to a Music-on-Hold category.

        Sends a multipart ``POST`` to ``/pbxapi/musiconhold`` with the file
        attached — bypassing the JSON body used by ``_request``.

        :param category: MOH category name (directory under
            ``/var/lib/asterisk/moh/``).
        :param file_path: Local path to the audio file to upload.
        :param reload: Whether to trigger a config reload after the upload.
        :return: Server response.
        """
        url = urljoin(self.base_url, "musiconhold")
        effective_reload = False if self._batch_mode else reload

        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {
                    "category": category,
                    "reload": "true" if effective_reload else "false",
                }
                response = self.session.post(
                    url,
                    files=files,
                    data=data,
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                )
            response.raise_for_status()
            return self._safe_json_parse(response) or {}
        except FileNotFoundError:
            return {"error": f"File not found: {file_path}"}
        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "response": getattr(e.response, "text", "")}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            return {"error": f"Network error uploading MOH file: {e}"}

    # ------------------------------------------------------------------
    # Dynamic method generator
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """
        Magic method to handle calls like ``get_extensions()``,
        ``create_ringgroups()``, ``update_trunks()``, ``delete_ivr()``, etc.

        Raises ``NotImplementedError`` for write operations on read-only
        resources, giving a clear client-side error instead of a cryptic
        HTTP 405 from the server.
        """
        if name.startswith("get_"):
            resource = name[4:]
            return lambda resource_id=None, fields=None: self.get_resource(resource, resource_id, fields)

        if name.startswith("create_"):
            resource = name[7:]
            if resource in READ_ONLY_RESOURCES:
                raise NotImplementedError(
                    f"Resource '{resource}' is read-only. Only GET operations are supported."
                )
            if resource in GET_PUT_ONLY_RESOURCES:
                raise NotImplementedError(
                    f"Resource '{resource}' does not support POST. Use update_{resource}() instead."
                )
            return lambda data, reload=True: self.create_resource(resource, data, reload)

        if name.startswith("update_"):
            resource = name[7:]
            if resource in READ_ONLY_RESOURCES:
                raise NotImplementedError(
                    f"Resource '{resource}' is read-only. Only GET operations are supported."
                )
            return lambda resource_id, data, reload=True: self.update_resource(resource, resource_id, data, reload)

        if name.startswith("delete_"):
            resource = name[7:]
            if resource in READ_ONLY_RESOURCES:
                raise NotImplementedError(
                    f"Resource '{resource}' is read-only. Only GET operations are supported."
                )
            if resource in GET_PUT_ONLY_RESOURCES:
                raise NotImplementedError(
                    f"Resource '{resource}' does not support DELETE. Use update_{resource}() instead."
                )
            return lambda resource_id, reload=True: self.delete_resource(resource, resource_id, reload)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# ---------------------------------------------------------------------------
# Complete resource catalogue (from /pbxapi/ controllers — v0.2.0)
#
# FULL CRUD (GET, POST, PUT, DELETE, SEARCH):
#   announcements, blacklist, bosssecretary, callback, callflow, cidlookup,
#   classofservice, conferences, customdestinations, customextensions,
#   dahdichanneldids, dialplaninjection, disa, dynamicroutes, extensions,
#   inboundroutes, ivr, languages, mailboxes, miscapplications,
#   miscdestinations, musiconhold, outboundroutes, paging, parkinglots,
#   pinsets, queuepriorities, queues, recordingrules, recordings, ringgroups,
#   setcallerid, timeconditions, timegroups, trunks, vmblast, writequeuelog
#
# GET + PUT only (no POST / DELETE):
#   classofserviceadmin, routecongestionmessages
#
# GET / SEARCH only (read-only):
#   alldestinations, allextensions, featurecodes, modules, systemrecordings
#
# MANAGER/* (AMI wrapper — use client.manager.<action>()):
#   queuestatus, status, extensionstate, dbget, dbput, dbdel, dbdeltree,
#   dbshow, queueadd, queueremove, queuepause, queueunpause, queuelog,
#   reload, hangup, getvar, userevent, originate
# ---------------------------------------------------------------------------
