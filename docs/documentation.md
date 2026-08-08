# Issabel Python Client — Documentation (v0.2.0)

The `issabel-client` is a Python library for consuming the Issabel PBX REST API (`pbxapi`). It features dynamic method generation, batch provisioning, an AMI wrapper, and robust error handling.

---

## Table of Contents

1. [Installation](#installation)
2. [Initialization](#initialization)
3. [Authentication](#authentication)
4. [Resource Operations (CRUD)](#resource-operations-crud)
5. [Batch Provisioning](#batch-provisioning)
6. [AMI Wrapper (`client.manager`)](#ami-wrapper-clientmanager)
7. [Search](#search)
8. [File Upload (Music-on-Hold)](#file-upload-music-on-hold)
9. [Resource Catalogue](#resource-catalogue)
10. [Error Handling](#error-handling)

---

## Installation

```bash
pip install issabel_client
```

Or from source for development:

```bash
git clone https://github.com/tsuriu/issabel_client.git
cd issabel_client
pip install -e .[dev]
```

---

## Initialization

```python
from issabel_client import IssabelClient

client = IssabelClient(
    base_url="192.168.1.100",
    use_ssl=True,           # Use HTTPS (default: True)
    verify_ssl=False,       # Verify SSL certificate (default: False — common for self-signed PBX certs)
    timeout=30,             # Request timeout in seconds (default: 30)
)
```

### Context Manager (recommended)

The client implements `__enter__`/`__exit__`, which automatically closes the underlying `requests.Session`:

```python
with IssabelClient("192.168.1.100", use_ssl=False) as client:
    client.authenticate("admin", "password")
    extensions = client.get_extensions()
```

---

## Authentication

### Login

```python
client.authenticate("admin", "your_password")
```

- Stores `access_token` and `refresh_token` internally.
- Raises `ValueError` on invalid credentials (HTTP 403).
- Raises `ValueError` on network errors.

### Check Session State

```python
status = client.check_auth_status()
# Returns current token info or {"status": "unauthorized"}
```

### Token Renewal

Token renewal is **automatic**: the client detects HTTP 401 responses or legacy `{"status": "expired"}` bodies and calls `renew_token()` transparently. If renewal fails, `AuthenticationError` is raised.

---

## Resource Operations (CRUD)

### Dynamic Methods

The client uses `__getattr__` to generate CRUD methods on the fly for any resource:

| Method | Signature | HTTP |
|--------|-----------|------|
| `get_<resource>` | `(resource_id=None, fields=None)` | GET |
| `create_<resource>` | `(data, reload=True)` | POST |
| `update_<resource>` | `(resource_id, data, reload=True)` | PUT |
| `delete_<resource>` | `(resource_id, reload=True)` | DELETE |

### Examples

```python
# List all extensions
extensions = client.get_extensions()

# Get a specific extension
ext = client.get_extensions(resource_id=2000)

# Get only specific fields
ext = client.get_extensions(resource_id=2000, fields=["name", "extension"])

# Create
client.create_extensions({
    "extension": "2000",
    "name": "John Doe",
    "secret": "pswd123",
    "tech": "sip",
})

# Update
client.update_extensions("2000", {"name": "John Updated"})

# Delete one
client.delete_extensions("2000")

# Delete multiple (comma-joined in URL path)
client.delete_resource("ivr", ["1", "2", "3"])
```

### Reload Control

Every write operation (`POST`, `PUT`, `DELETE`) triggers an Asterisk config reload by default. Pass `reload=False` to suppress it:

```python
client.create_extensions({"extension": "2001", ...}, reload=False)
client.delete_extensions("2001", reload=False)
```

> **Important:** When `reload=False`, the field `"reload": "false"` is explicitly included in the request body. The Issabel API applies reload by default when the field is absent, so omitting it is not equivalent to disabling it.

---

## Batch Provisioning

For bulk operations (importing hundreds of extensions, for example), use `client.batch()` to suppress per-operation reloads and fire a **single reload at the end**:

```python
with client.batch():
    for ext_num in range(1001, 1100):
        client.create_extensions({
            "extension": str(ext_num),
            "name": f"User {ext_num}",
            "secret": "s3cr3t",
        })
# ↑ manager/reload dispatched automatically here — Asterisk updated once.
```

**How it works:**

1. Entering the `with` block sets an internal flag (`_batch_mode = True`).
2. All `POST`/`PUT`/`DELETE` calls within the block receive `reload="false"` regardless of what the caller passes.
3. On exit, `client.manager.reload()` is called exactly **once**, applying all pending changes.
4. If an exception escapes the block, the reload is still attempted (so partial changes are not left in limbo), and the original exception propagates normally.

---

## AMI Wrapper (`client.manager`)

The `client.manager` namespace exposes all 18 Asterisk Manager Interface commands available at `/pbxapi/manager/{action}`:

### Available Actions

| Method | HTTP | Key Parameters |
|--------|------|----------------|
| `originate` | GET | `channel`, `extension`, `context`, `priority`, `timeout`, `callerid`, ... |
| `queuestatus` | GET | `queue` |
| `status` | GET | `channel` |
| `extensionstate` | GET | `extension`, `context`, `uniqueid` |
| `dbget` | GET | `family`, `key` |
| `dbput` | POST | `family`, `key`, `value` |
| `dbdel` | DELETE | `family`, `key` |
| `dbdeltree` | GET | `family` |
| `dbshow` | GET | `family` |
| `queueadd` | GET | `queue`, `interface`, `penalty`, `paused`, `membername`, `stateinterface` |
| `queueremove` | GET | `queue`, `interface` |
| `queuepause` | GET | `queue`, `interface` |
| `queueunpause` | GET | `queue`, `interface` |
| `queuelog` | GET | `queue`, `event`, `uniqueid`, `interface`, `message` |
| `reload` | GET | — |
| `hangup` | GET | `channel`, `cause` |
| `getvar` | GET | `channel`, `variable` |
| `userevent` | GET | `event`, + custom params |

### Examples

```python
# Originate a call
client.manager.originate(
    channel="SIP/1001",
    extension="1002",
    context="from-internal",
    priority=1,
)

# Read from AstDB
val = client.manager.dbget(family="MyFamily", key="MyKey")

# Write to AstDB
client.manager.dbput(family="MyFamily", key="MyKey", value="MyValue")

# Queue status
status = client.manager.queuestatus(queue="support")

# Hang up a call
client.manager.hangup(channel="SIP/1001-00000001")

# Manual full reload
client.manager.reload()
```

---

## Search

```python
# Search within any resource
results = client.search("extensions", "John")

# Limit fields returned
results = client.search("queues", "support", fields=["extension", "descr"])
```

---

## File Upload (Music-on-Hold)

Use `upload_moh_file()` to upload an audio file to a MOH category. This sends a `multipart/form-data` POST instead of JSON:

```python
client.upload_moh_file(
    category="default",
    file_path="/path/to/audio.wav",
    reload=True,
)
```

The file is read from the local filesystem and streamed to the server.

---

## Resource Catalogue

### Full CRUD (GET, POST, PUT, DELETE, SEARCH)

| Resource | ID Field | Notes |
|----------|----------|-------|
| `announcements` | `announcement_id` | |
| `blacklist` | `id` | |
| `bosssecretary` | `id_group` | |
| `callback` | `callback_id` | |
| `callflow` | `id` | Day/Night toggle |
| `cidlookup` | `cidlookup_id` | |
| `classofservice` | `context` | |
| `conferences` | `exten` | |
| `customdestinations` | `custom_dest` | |
| `customextensions` | `custom_exten` | |
| `dahdichanneldids` | `channel` | |
| `dialplaninjection` | `id` | |
| `disa` | `disa_id` | |
| `dynamicroutes` | `dynroute_id` | |
| `extensions` | `id` | |
| `inboundroutes` | `extension` | |
| `ivr` | `id` | |
| `languages` | `language_id` | |
| `mailboxes` | `extension` | |
| `miscapplications` | `miscapps_id` | |
| `miscdestinations` | `id` | |
| `musiconhold` | `id` | File-based; use `upload_moh_file()` for uploads |
| `outboundroutes` | `route_id` | |
| `paging` | `page_group` | |
| `parkinglots` | `id` | |
| `pinsets` | `pinsets_id` | |
| `queuepriorities` | `queueprio_id` | |
| `queues` | `extension` | |
| `recordingrules` | `id` | |
| `recordings` | `id` | |
| `ringgroups` | `grpnum` | |
| `setcallerid` | `cid_id` | |
| `timeconditions` | `id` | |
| `timegroups` | `id` | |
| `trunks` | `trunkid` | |
| `vmblast` | `grpnum` | |
| `writequeuelog` | `qlog_id` | |

### GET + PUT only (no POST / DELETE)

| Resource | Notes |
|----------|-------|
| `classofserviceadmin` | Use `update_classofserviceadmin()` |
| `routecongestionmessages` | Use `update_routecongestionmessages()` |

### Read-only (GET / SEARCH only)

These resources raise `NotImplementedError` on the **client side** if you attempt any write operation:

| Resource | Notes |
|----------|-------|
| `alldestinations` | All configured destinations (SQL view) |
| `allextensions` | All extensions (dynamic) |
| `featurecodes` | Feature codes |
| `modules` | Installed modules |
| `systemrecordings` | Audio files in `/var/lib/asterisk/sounds/custom/` |

### AMI Wrapper (`client.manager.*`)

See [AMI Wrapper](#ami-wrapper-clientmanager) section above.

---

## Error Handling

| Exception | When raised |
|-----------|-------------|
| `ValueError` | Invalid credentials (403), non-JSON response from server, network error during `authenticate()` |
| `AuthenticationError` | Token renewal fails (expired refresh token, network down during `renew_token()`) |
| `NotImplementedError` | Write operation on a read-only or GET+PUT-only resource |
| `AttributeError` | Unknown method name not matching any `get_`/`create_`/`update_`/`delete_` prefix |

All other HTTP and network errors in `_request()` are returned as a dict `{"error": "...", "response": "..."}` rather than raising exceptions.

```python
from issabel_client import IssabelClient
from issabel_client.client import AuthenticationError

try:
    client.authenticate("admin", "wrong")
except ValueError as e:
    print(f"Auth error: {e}")

try:
    result = client.get_extensions()
    if "error" in result:
        print(f"API error: {result['error']}")
except AuthenticationError as e:
    print(f"Token renewal failed: {e} — please re-authenticate.")
```
