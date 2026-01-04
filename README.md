[![PyPI version](https://img.shields.io/pypi/v/issabel_client.svg)](https://pypi.org/project/issabel_client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/issabel_client.svg)](https://pypi.org/project/issabel_client/)

A simple and functional Python Client to consume the Issabel PBX API. This Client provides a highly dynamic interface that automatically supports all available PBX resources.

## Features

- **Dynamic method generation**: Automatically supports all 40+ PBX resources (Extensions, Trunks, Queues, IVR, etc.).
- **Automatic token renewal**: Handles expired tokens seamlessly using the refresh token.
- **Full CRUD support**: Effortlessly list, create, update, and delete any PBX resource.
- **Configurable SSL**: Supports secure environments with optional certificate verification.
- **Resource Reloading**: Optionally trigger a PBX configuration reload after changes.

## Installation

```bash
pip install issabel_client
```

Or install from source for development:

```bash
git clone https://github.com/tsuriu/issabel_client.git
cd issabel_client
pip install -e .
```

## Quick Start

```python
from issabel_client import IssabelClient

# Initialize the client
client = IssabelClient("your-pbx-ip", use_ssl=False)

# Authenticate
client.authenticate("admin", "yourpassword")

# List all extensions
extensions = client.get_extensions()
print(extensions)

# Create a new extension
new_ext = client.create_extensions({
    "name": "John Doe",
    "extension": "2000",
    "secret": "pswd123"
})
```

## Documentation

For detailed usage instructions, advanced configuration, and a full list of supported resources, please see our [Documentation](docs/documentation.md).

## Examples

Check the `examples/` directory for ready-to-use scripts:
- [example_usage.py](examples/example_usage.py)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
