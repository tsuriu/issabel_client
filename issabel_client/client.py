import requests
import json
import urllib3
from urllib.parse import urljoin
from typing import Optional, Any, Dict, List, Union

# Disable insecure request warnings for self-signed certificates (common in PBX environments)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__version__ = "0.1.0"

class IssabelClient:
    """
    Python Client for Issabel PBX API.
    
    This client provides a dynamic interface to interact with all resources
    available in the Issabel PBX API.
    """
    def __init__(self, base_url: str, use_ssl: bool = True, verify_ssl: bool = False):
        """
        Initialize the Issabel PBX API Client.
        
        :param base_url: The base URL or IP of the Issabel server.
        :param use_ssl: Whether to use HTTPS (default True).
        :param verify_ssl: Whether to verify SSL certificates (default False).
        """
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{base_url.rstrip('/')}/pbxapi/"
        self.verify_ssl = verify_ssl
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session = requests.Session()

    def _safe_json_parse(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON from a response.
        
        :param response: The requests Response object.
        :return: A dictionary containing the JSON data, or None if the response is empty.
        """
        if not response.content:
            return None
        
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return {"error": "Invalid JSON response", "content": response.text}

    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with the PBX API and retrieve access tokens.
        
        :param username: PBX API username.
        :param password: PBX API password.
        :return: The authentication result containing tokens.
        :raises ValueError: If authentication fails.
        """
        url = urljoin(self.base_url, "authenticate")
        data = {
            "user": username,
            "password": password
        }
        response = self.session.post(url, data=data, verify=self.verify_ssl)
        response.raise_for_status()
        
        result = self._safe_json_parse(response)
        if result and "error" in result:
             raise ValueError(f"Authentication failed: Server returned non-JSON response. Content: {result['content'][:200]}")

        self.access_token = result.get("access_token") if result else None
        self.refresh_token = result.get("refresh_token") if result else None
        
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
        return result or {}

    def renew_token(self) -> Dict[str, Any]:
        """
        Renew the access token using the refresh token.
        
        :return: The renewal result.
        :raises ValueError: If tokens are missing.
        """
        if not self.refresh_token or not self.access_token:
            raise ValueError("No refresh token or access token available. Authenticate first.")
        
        url = urljoin(self.base_url, f"authenticate/renewtoken?refresh_token={self.refresh_token}&access_token={self.access_token}")
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        result = self._safe_json_parse(response)
        if result and result.get("status") == "authorized":
            self.access_token = result.get("access_token")
            self.refresh_token = result.get("refresh_token")
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
        return result or {}

    def _request(
        self, 
        method: str, 
        resource: str, 
        path_id: Optional[Union[str, int]] = None, 
        data: Optional[Dict[str, Any]] = None, 
        params: Optional[Dict[str, Any]] = None, 
        reload: bool = True
    ) -> Dict[str, Any]:
        """
        Internal helper for making API requests.
        
        :param method: HTTP method (GET, POST, PUT, DELETE).
        :param resource: API resource name.
        :param path_id: Optional resource ID for the URL path.
        :param data: JSON payload for POST/PUT requests.
        :param params: Query parameters for the request.
        :param reload: Whether to trigger a config reload (True by default).
        :return: The parsed JSON response.
        """
        path = resource
        if path_id:
            path = f"{resource}/{path_id}"
        
        url = urljoin(self.base_url, path)
        
        # Merge reload into data if it's a POST/PUT request
        if method in ["POST", "PUT"]:
            if data is None:
                data = {}
            if reload:
                data["reload"] = "true"
        
        headers = {"Content-Type": "application/json"}
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                verify=self.verify_ssl
            )
            
            # Auto-renew token if expired
            if response.status_code == 401:
                self.renew_token()
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                    verify=self.verify_ssl
                )
            
            # Check for expired token in 200 response (legacy behavior)
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
                        verify=self.verify_ssl
                    )
                
            response.raise_for_status()
            
            return self._safe_json_parse(response) or {}
        except requests.exceptions.HTTPError as e:
            return {"error": str(e), "response": getattr(response, 'text', '')}

    def search(self, resource: str, term: str, fields: Optional[Union[str, List[str]]] = None) -> Dict[str, Any]:
        """
        Search for a term in a resource.
        
        :param resource: The resource to search in (e.g., 'extensions').
        :param term: The search term.
        :param fields: Optional list of fields to return.
        :return: Search results.
        """
        params = {}
        if fields:
            params["fields"] = fields if isinstance(fields, str) else ",".join(fields)
        
        return self._request("GET", f"{resource}/search/{term}", params=params)

    # Generic Resource CRUD methods
    def get_resource(
        self, 
        resource: str, 
        resource_id: Optional[Union[str, int]] = None, 
        fields: Optional[Union[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """Get one or all records for a resource."""
        params = {}
        if fields:
            params["fields"] = fields if isinstance(fields, str) else ",".join(fields)
        return self._request("GET", resource, path_id=resource_id, params=params)

    def create_resource(self, resource: str, data: Dict[str, Any], reload: bool = True) -> Dict[str, Any]:
        """Create a new record for a resource."""
        return self._request("POST", resource, data=data, reload=reload)

    def update_resource(
        self, 
        resource: str, 
        resource_id: Union[str, int], 
        data: Dict[str, Any], 
        reload: bool = True
    ) -> Dict[str, Any]:
        """Update an existing record for a resource."""
        return self._request("PUT", resource, path_id=resource_id, data=data, reload=reload)

    def delete_resource(self, resource: str, resource_id: Union[str, int, List[Union[str, int]]], reload: bool = True) -> Dict[str, Any]:
        """Delete one or more records for a resource."""
        # resource_id can be a single ID or a list of IDs
        if isinstance(resource_id, list):
            resource_id = ",".join(map(str, resource_id))
        return self._request("DELETE", resource, path_id=resource_id, reload=reload)

    # Dynamic Method Generator for all controllers
    def __getattr__(self, name: str) -> Any:
        """
        Magic method to handle calls like get_extensions(), create_ringgroups(), etc.
        """
        if name.startswith("get_"):
            resource = name[4:]
            return lambda resource_id=None, fields=None: self.get_resource(resource, resource_id, fields)
        elif name.startswith("create_"):
            resource = name[7:]
            return lambda data, reload=True: self.create_resource(resource, data, reload)
        elif name.startswith("update_"):
            resource = name[7:]
            return lambda resource_id, data, reload=True: self.update_resource(resource, resource_id, data, reload)
        elif name.startswith("delete_"):
            resource = name[7:]
            return lambda resource_id, reload=True: self.delete_resource(resource, resource_id, reload)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# List of endpoints for reference (from controllers directory):
# announcements, blacklist, bosssecretary, callback, callflow, cidlookup, 
# classofservice, classofserviceadmin, conferences, customdestinations, 
# customextensions, dahdichanneldids, dialplaninjection, disa, dynamicroutes, 
# extensions, featurecodes, inboundroutes, ivr, languages, mailboxes, 
# manager, miscapplications, miscdestinations, modules, musiconhold, 
# outboundroutes, paging, parkinglots, pinsets, queuepriorities, queues, 
# recordingrules, recordings, ringgroups, routecongestionmessages, 
# setcallerid, systemrecordings, timeconditions, timegroups, trunks, 
# vmblast, writequeuelog
