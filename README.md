[![PyPI version](https://img.shields.io/pypi/v/issabel_client.svg)](https://pypi.org/project/issabel_client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/issabel_client.svg)](https://pypi.org/project/issabel_client/)

A Python client for the Issabel PBX REST API (`pbxapi`). Supports dynamic CRUD for all 40+ resources, batch provisioning with a single final reload, and a full Asterisk Manager Interface (AMI) wrapper.

## Features

- **Dynamic method generation** — Automatic CRUD for all PBX resources (`get_`, `create_`, `update_`, `delete_`).
- **Batch provisioning** — `with client.batch():` runs N write operations with zero per-call reloads; one `manager/reload` fires automatically at the end.
- **AMI wrapper** (`client.manager`) — All 18 Asterisk Manager actions: `originate`, `queuestatus`, `dbget`, `dbput`, `hangup`, `reload`, and more.
- **Automatic token renewal** — Detects HTTP 401 and legacy `{"status": "expired"}` responses and renews transparently.
- **Read-only guards** — `NotImplementedError` raised client-side for write attempts on read-only resources.
- **Configurable timeout** — All HTTP calls share a single `timeout` setting.
- **Context manager** — `with IssabelClient(...) as client:` closes the session on exit.
- **SSL support** — Configurable certificate verification (self-signed certs common on PBX appliances).

## Installation

```bash
pip install issabel_client
```

Or from source:

```bash
git clone https://github.com/tsuriu/issabel_client.git
cd issabel_client
pip install -e .[dev]
```

## Quick Start

```python
from issabel_client import IssabelClient

with IssabelClient("your-pbx-ip", use_ssl=True, verify_ssl=False) as client:
    client.authenticate("admin", "yourpassword")

    # List all extensions
    extensions = client.get_extensions()

    # Create one with immediate reload (default)
    client.create_extensions({"extension": "2000", "name": "John Doe", "secret": "pswd123"})

    # Batch provisioning — single reload at the end
    with client.batch():
        for ext in range(3001, 3100):
            client.create_extensions({"extension": str(ext), "name": f"User {ext}", "secret": "s3cr3t"})
    # ↑ Asterisk reloaded exactly once here

    # AMI: originate a call
    client.manager.originate(channel="SIP/1001", extension="1002", context="from-internal", priority=1)

    # AMI: reload Asterisk manually
    client.manager.reload()
```

## Documentation

Full usage guide, payload schemas, and the complete resource catalogue are in [docs/documentation.md](docs/documentation.md).

## Examples

Ready-to-run scripts are in the `examples/` directory:
- [example_usage.py](examples/example_usage.py)

## Resource Capabilities

| Category | Resources |
|----------|-----------|
| **Full CRUD** | `announcements`, `blacklist`, `bosssecretary`, `callback`, `callflow`, `cidlookup`, `classofservice`, `conferences`, `customdestinations`, `customextensions`, `dahdichanneldids`, `dialplaninjection`, `disa`, `dynamicroutes`, `extensions`, `inboundroutes`, `ivr`, `languages`, `mailboxes`, `miscapplications`, `miscdestinations`, `musiconhold`, `outboundroutes`, `paging`, `parkinglots`, `pinsets`, `queuepriorities`, `queues`, `recordingrules`, `recordings`, `ringgroups`, `setcallerid`, `timeconditions`, `timegroups`, `trunks`, `vmblast`, `writequeuelog` |
| **GET + PUT only** | `classofserviceadmin`, `routecongestionmessages` |
| **Read-only** | `alldestinations`, `allextensions`, `featurecodes`, `modules`, `systemrecordings` |
| **AMI wrapper** | `client.manager.originate`, `.queuestatus`, `.dbget`, `.dbput`, `.dbdel`, `.reload`, `.hangup`, and 11 more |

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull Requests are welcome! Please run `pytest` and `flake8` before submitting.
