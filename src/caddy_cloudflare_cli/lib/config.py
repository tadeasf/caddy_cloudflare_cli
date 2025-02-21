"""
Configuration management for Caddy Cloudflare CLI
"""
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict

import yaml
from rich.prompt import Prompt

CONFIG_DIR = Path("~/.config/caddy-cloudflare").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DATA_DIR = Path("~/.local/share/caddy-cloudflare").expanduser()
CACHE_DIR = Path("~/.cache/caddy-cloudflare").expanduser()

@dataclass
class Config:
    """Configuration data"""
    # DNS settings
    dns_provider: str = "cloudflare"
    cloudflare_token: str = ""
    domain: str = ""
    
    # Proxy settings
    proxy_type: str = "caddy"
    proxy_mode: str = "user"  # or "system"
    
    # Installation paths
    data_dir: Path = DATA_DIR
    config_dir: Path = CONFIG_DIR
    cache_dir: Path = CACHE_DIR
    
    # System settings
    email: str = ""
    
    @classmethod
    def load(cls) -> 'Config':
        """Load configuration from file"""
        if not CONFIG_FILE.exists():
            raise ConfigError("Configuration not found. Please run 'caddy-cloudflare init' first.")
        
        with open(CONFIG_FILE) as f:
            data = yaml.safe_load(f)
            
        # Convert path strings to Path objects
        for key in ['data_dir', 'config_dir', 'cache_dir']:
            if key in data:
                data[key] = Path(data[key]).expanduser()
        
        return cls(**data)
    
    def save(self):
        """Save configuration to file"""
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and ensure paths are strings
        data = asdict(self)
        for key in ['data_dir', 'config_dir', 'cache_dir']:
            data[key] = str(data[key])
        
        with open(CONFIG_FILE, 'w') as f:
            yaml.safe_dump(data, f)
    
    @classmethod
    def initialize_interactive(cls) -> 'Config':
        """Initialize configuration interactively"""
        print("Welcome to Caddy Cloudflare CLI setup!")
        print("\nPlease provide the following information:")
        
        config = cls(
            cloudflare_token=Prompt.ask(
                "\nCloudflare API token (with Zone.DNS:Edit and Zone.Zone:Read permissions)"
            ),
            domain=Prompt.ask("Domain name (e.g., example.com)"),
            email=Prompt.ask("Email address (for SSL certificates)"),
            proxy_mode=Prompt.ask(
                "Installation mode",
                choices=["user", "system"],
                default="user"
            )
        )
        
        # Create necessary directories
        for directory in [config.data_dir, config.config_dir, config.cache_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        config.save()
        
        return config
    
    def get_proxy_dirs(self) -> Dict[str, Path]:
        """Get proxy-specific directories"""
        return {
            'config': self.config_dir / 'proxy',
            'data': self.data_dir / 'proxy',
            'cache': self.cache_dir / 'proxy'
        }
    
    def get_binary_path(self) -> Path:
        """Get path to proxy binary"""
        return self.data_dir / 'bin' / ('caddy' if os.name != 'nt' else 'caddy.exe')

class ConfigError(Exception):
    """Configuration error"""
    pass
