# Caddy Cloudflare CLI

A powerful CLI tool for setting up and managing Cloudflare DNS records with Caddy reverse proxy. Easily deploy local services with public domains, automate DNS configuration, and manage SSL certificates using Cloudflare's API.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Features

- 🚀 Create and manage Cloudflare DNS records with ease
- 🔒 Automatic SSL certificate provisioning via Caddy and Cloudflare
- 🌐 Expose local services to the internet in seconds
- 🛡️ Leverage Cloudflare's security and CDN benefits
- 🔄 Simple commands to deploy, list, and remove domains

## Installation

```bash
# Install with pip
pip install caddy-cloudflare-cli

# Or install with development dependencies
pip install caddy-cloudflare-cli[dev]
```

## Cloudflare Setup Guide

Before using this tool, you'll need a Cloudflare account and domain. Follow these steps:

### 1. Register a Domain

If you don't already have a domain:

1. Purchase a domain from any domain registrar (Namecheap, GoDaddy, etc.)
2. We recommend choosing a domain registrar based on price and their ease of changing nameservers

### 2. Add Domain to Cloudflare

1. Create a [Cloudflare account](https://dash.cloudflare.com/sign-up) if you don't have one
2. Log in to Cloudflare and click "Add a Site"
3. Enter your domain name and click "Add Site"
4. Select a plan (the Free plan works fine for this tool)
5. Cloudflare will scan for existing DNS records

### 3. Update Nameservers

1. Cloudflare will provide you with nameservers (e.g., `cruz.ns.cloudflare.com` and `tim.ns.cloudflare.com`)
2. Go to your domain registrar's website
3. Find the nameserver settings for your domain
4. Replace the current nameservers with Cloudflare's nameservers
5. Save the changes (propagation can take up to 24 hours)

### 4. Create API Tokens

For the most secure setup, create dedicated API tokens:

1. Go to your [Cloudflare dashboard](https://dash.cloudflare.com/)
2. Navigate to "My Profile" → "API Tokens"
3. Click "Create Token"
4. Choose "Create Custom Token"
5. Give your token a name (e.g., "Caddy DNS Token")
6. Under "Permissions", add:
   - Zone - DNS - Edit
7. Under "Zone Resources", select:
   - Include - Specific zone - Your domain
8. Click "Continue to Summary" and then "Create Token"
9. Copy the token value (you won't be able to see it again!)

## Usage

### Initial Setup

```bash
# Initialize configuration
caddy-cloudflare init
```

Follow the interactive prompts to configure your Cloudflare credentials and domain.

### Install Caddy

```bash
# Install Caddy locally
caddy-cloudflare install

# Or install Caddy system-wide (requires sudo)
sudo caddy-cloudflare install --system
```

### Deploy a Service

```bash
# Deploy with interactive prompts
caddy-cloudflare deploy

# Deploy with specific options
caddy-cloudflare deploy --subdomain myapp --port 3000

# Using a custom IP (instead of auto-detection)
caddy-cloudflare deploy --ip 203.0.113.1
```

### Manage Deployments

```bash
# List all deployments
caddy-cloudflare list

# Show all DNS records (not just deployments)
caddy-cloudflare list --all

# Delete a deployment
caddy-cloudflare delete myapp
```

### Proxy Management

```bash
# Start the Caddy proxy
caddy-cloudflare proxy start

# Check proxy status
caddy-cloudflare proxy status

# Stop the proxy
caddy-cloudflare proxy stop

# Reload proxy configuration
caddy-cloudflare proxy reload
```

### Troubleshooting

```bash
# Run diagnostic checks
caddy-cloudflare debug
```

## Advanced Usage

### Using Environment Variables

You can use environment variables instead of storing credentials in config files:

```bash
# API Token method (recommended)
export CLOUDFLARE_API_TOKEN="your-api-token"

# Least privilege method (recommended)
export CLOUDFLARE_ZONE_TOKEN="your-zone-token"
export CLOUDFLARE_DNS_TOKEN="your-dns-token"

# Global API key method (legacy)
export CLOUDFLARE_API_KEY="your-global-api-key"
export CLOUDFLARE_EMAIL="your-email@example.com"

# Domain configuration
export CLOUDFLARE_DOMAIN="yourdomain.com"
```

## Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/my-new-feature`
5. Submit a pull request

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/caddy-cloudflare-cli.git
cd caddy-cloudflare-cli

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Areas for Contribution

We're especially interested in contributions for:

1. **New DNS Providers**: Add support for more DNS providers beyond Cloudflare
2. **New Proxy Providers**: Add support for additional reverse proxy solutions
3. **Bug Fixes**: Help identify and fix bugs
4. **Documentation**: Improve documentation and examples
5. **Testing**: Add more tests and improve test coverage

## Creating Issues

If you find a bug or want to request a feature, please create an issue:

```markdown
## Description
A clear description of the issue or feature request

## Steps to Reproduce (for bugs)
1. Step 1
2. Step 2
3. ...

## Expected Behavior
What you expected to happen

## Actual Behavior
What actually happened

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.2]
- Package version: [e.g., 0.1.0]
```

## TODO

- [ ] Add support for wedos.cz WAPI DNS provider
- [ ] Implement direct Cloudflare Tunnel support
- [ ] Add support for more complex Caddy configurations
- [ ] Create Docker container for easier deployment
- [ ] Implement concurrent multi-domain management

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
