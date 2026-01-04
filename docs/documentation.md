# Issabel Python Client Documentation

The `issabel-client` is a simple and functional Python library to consume the Issabel PBX API. It provides a highly dynamic interface that automatically supports all available PBX resources.

## Features

- **Dynamic Method Generation**: No need to wait for library updates when new endpoints are added to the PBX.
- **Automatic Authentication**: Handles login and token management.
- **Token Renewal**: Automatically renews expired tokens using the refresh token.
- **SSL/TLS Support**: Configurable SSL verification for secure environments.
- **Reloading**: Automatically applies changes to the PBX configuration.

## Usage

### Initialization

```python
from issabel_client import IssabelClient

# Replace with your Issabel server details
client = IssabelClient(
    base_url="192.168.1.100", 
    use_ssl=True, 
    verify_ssl=False  # Set to True if using valid certificates
)

# Authenticate
client.authenticate("admin", "your_password")
```

### Resource Operations

The client uses `__getattr__` to dynamically support any resource available in the PBX API. The naming convention is:
- `get_<resource>(id=None, fields=None)`
- `create_<resource>(data, reload=True)`
- `update_<resource>(id, data, reload=True)`
- `delete_<resource>(id, reload=True)`

#### Extensions

```python
# List all extensions
extensions = client.get_extensions()

# Get a specific extension
extension = client.get_extensions(2000)

# Create a new extension
client.create_extensions({
    "name": "John Doe",
    "extension": "2000",
    "secret": "pswd123"
})

# Update an extension
client.update_extensions(2000, {"name": "John Updated"})

# Delete an extension
client.delete_extensions(2000)
```

#### Ring Groups

```python
# List all ring groups
groups = client.get_ringgroups()

# Create a new ring group
client.create_ringgroups({
    "name": "Sales",
    "extension_list": ["100", "101"]
})
```

### Search

You can search within any resource:

```python
results = client.search("extensions", "John")
```

### Error Handling

The client includes a `_safe_json_parse` helper to handle cases where the server might return non-JSON responses (e.g., HTML error pages). Errors will include the status code and the first few characters of the response body for easier debugging.

```python
try:
    client.authenticate("admin", "wrong_password")
except Exception as e:
    print(f"Error: {e}")
```

## Available Resources
The following resources are currently supported based on the PBX controllers:
- `announcements`
- `blacklist`
- `bosssecretary`
- `callback`
- `callflow`
- `cidlookup`
- `classofservice`
- `conferences`
- `extensions`
- `inboundroutes`
- `ivr`
- `queues`
- `ringgroups`
- `trunks`
- ... and many more.
