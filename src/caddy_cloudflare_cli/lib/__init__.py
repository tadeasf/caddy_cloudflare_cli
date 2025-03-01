"""
Core library for Caddy Cloudflare CLI
"""

from .config import Config, ConfigError
from .factory import DNSProviderFactory, ProxyProviderFactory

# Import utils module, not individual functions
import caddy_cloudflare_cli.lib.utils as utils

__all__ = [
    "Config", 
    "ConfigError",
    "DNSProviderFactory",
    "ProxyProviderFactory",
    "utils"
]
