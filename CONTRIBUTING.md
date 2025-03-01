# Contributing to Caddy Cloudflare CLI

Thank you for considering contributing to Caddy Cloudflare CLI! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project. We aim to foster an inclusive and welcoming community.

## How Can I Contribute?

### Reporting Bugs

If you find a bug, please create an issue using the bug report template. Include as much detail as possible:

- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, etc.)
- Any relevant logs or error messages

### Suggesting Enhancements

Have an idea for a new feature? Create an issue using the feature request template and describe your idea in detail.

### Pull Requests

We actively welcome pull requests!

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Add tests for your changes
5. Run the tests: `pytest`
6. Push your branch: `git push origin feature/your-feature-name`
7. Submit a pull request

## Development Setup

1. Clone your fork of the repository
2. Install the package in development mode:

```bash
pip install -e ".[dev]"
```

3. Install development dependencies:

```bash
pip install pytest pytest-cov ruff
```

## Project Structure

- `src/caddy_cloudflare_cli/` - Main package directory
  - `cli.py` - Command-line interface definitions
  - `lib/` - Core library code
    - `cmd/` - Command implementations
    - `dns/` - DNS provider implementations
    - `proxy/` - Proxy provider implementations
    - `config.py` - Configuration management
    - `utils.py` - Utility functions

## Adding a New DNS Provider

One of the most valuable contributions you can make is to add support for a new DNS provider. Here's how:

1. Create a new file in `src/caddy_cloudflare_cli/lib/dns/` named after your provider (e.g., `wedos_api_handler.py`)
2. Implement the provider class, inheriting from `DNSProvider` base class
3. Implement all the required methods from the base class
4. Update the factory in `factory.py` to include your new provider
5. Add tests for your provider
6. Update documentation to include your new provider

Example:

```python
# src/caddy_cloudflare_cli/lib/dns/wedos_api_handler.py
from typing import List, Optional
from .base import DNSProvider, DNSRecord, DNSError

class WedosDNS(DNSProvider):
    """Wedos DNS Provider Implementation"""
    
    def __init__(self, config):
        self.config = config
        # Initialize Wedos API client
        # ...
    
    def create_record(self, subdomain, record_type="A", content="127.0.0.1", 
                     proxied=True, ttl=1) -> DNSRecord:
        # Implementation...
        pass
    
    def delete_record(self, record_id) -> bool:
        # Implementation...
        pass
    
    # Implement other required methods...
```

Then register it in the factory:

```python
# src/caddy_cloudflare_cli/lib/factory.py
from .dns.wedos_api_handler import WedosDNS

class DNSProviderFactory(ProviderFactory):
    _providers = {
        'cloudflare': CloudflareDNS,
        'wedos': WedosDNS
    }
    # ...
```

## Adding a New Proxy Provider

Similarly, you can add support for a new reverse proxy:

1. Create a new directory in `src/caddy_cloudflare_cli/lib/proxy/` for your provider
2. Implement the provider class, inheriting from `ReverseProxy` base class
3. Implement all required methods
4. Update the factory to include your new provider
5. Add tests for your provider
6. Update documentation

## Code Style

We use `ruff` for linting. Please ensure your code follows our style guidelines:

```bash
ruff check .
```

## Testing

Please write tests for your changes. We use `pytest` for testing:

```bash
pytest
```

## Upcoming Features

We're particularly interested in contributions for:

- Adding support for wedos.cz WAPI DNS provider
- Implementing direct Cloudflare Tunnel support
- Adding support for more complex Caddy configurations
- Creating a Docker container for easier deployment

## Questions?

If you have any questions about contributing, please open an issue with the label "question".
