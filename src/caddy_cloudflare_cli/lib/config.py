"""
Configuration management for Caddy Cloudflare CLI
"""
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
import yaml
from rich.prompt import Prompt

# Load environment variables from .env file
load_dotenv()

CONFIG_DIR = Path("~/.config/caddy-cloudflare").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DATA_DIR = Path("~/.local/share/caddy-cloudflare").expanduser()
CACHE_DIR = Path("~/.cache/caddy-cloudflare").expanduser()

@dataclass
class Config:
    """Configuration data"""
    # DNS settings
    dns_provider: str = "cloudflare"
    cloudflare_token: str = ""  # API Token (preferred)
    cloudflare_api_key: str = ""  # Global API Key (legacy)
    cloudflare_api_email: str = ""  # Required for Global API Key
    cloudflare_zone_token: str = ""  # Zone:Read token
    cloudflare_dns_token: str = ""  # DNS:Edit token
    domain: str = ""
    public_ip: str = ""  # Public IP for DNS records
    
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
        
        # Create config from file
        config = cls(**data)
        
        # Override with environment variables if they exist
        # This gives precedence to environment variables over the config file
        env_token = os.getenv("CLOUDFLARE_API_TOKEN")
        env_key = os.getenv("CLOUDFLARE_API_KEY")
        env_email = os.getenv("CLOUDFLARE_EMAIL")
        env_domain = os.getenv("CLOUDFLARE_DOMAIN")
        env_public_ip = os.getenv("CLOUDFLARE_PUBLIC_IP")
        env_zone_token = os.getenv("CLOUDFLARE_ZONE_TOKEN")
        # Also check for misspelled environment variable as fallback
        if not env_zone_token:
            env_zone_token = os.getenv("CLOUDLFLARE_ZONE_TOKEN")
        env_dns_token = os.getenv("CLOUDFLARE_DNS_TOKEN")
        
        if env_token:
            config.cloudflare_token = env_token
        if env_key:
            config.cloudflare_api_key = env_key
        if env_email:
            config.cloudflare_api_email = env_email
        if env_domain:
            config.domain = env_domain
        if env_public_ip:
            config.public_ip = env_public_ip
        if env_zone_token:
            config.cloudflare_zone_token = env_zone_token
        if env_dns_token:
            config.cloudflare_dns_token = env_dns_token
            
        return config
    
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
        
        # Get default values from environment
        env_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        env_key = os.getenv("CLOUDFLARE_API_KEY", "")
        env_email = os.getenv("CLOUDFLARE_EMAIL", "")
        env_domain = os.getenv("CLOUDFLARE_DOMAIN", "")
        env_public_ip = os.getenv("CLOUDFLARE_PUBLIC_IP", "")
        env_zone_token = os.getenv("CLOUDFLARE_ZONE_TOKEN", "")
        # Also check for misspelled environment variable as fallback
        if not env_zone_token:
            env_zone_token = os.getenv("CLOUDLFLARE_ZONE_TOKEN", "")
        env_dns_token = os.getenv("CLOUDFLARE_DNS_TOKEN", "")
        
        # Determine default authentication method based on available env vars
        default_auth = "dual" if (env_zone_token and env_dns_token) else "token" if env_token else "global" if (env_key and env_email) else "dual"
        
        auth_type = Prompt.ask(
            "\nAuthentication type",
            choices=["dual", "token", "global"],
            default=default_auth
        )
        
        # Default domain to empty if not in env
        domain_default = env_domain if env_domain else ""
        # Default email to Cloudflare email if available
        email_default = env_email if env_email else ""
        # Default public IP to env if available, otherwise leave empty
        public_ip_default = env_public_ip if env_public_ip else ""
        
        config_data = {
            'domain': Prompt.ask("Domain name (e.g., example.com)", default=domain_default),
            'email': Prompt.ask("Email address (for SSL certificates)", default=email_default),
            'public_ip': Prompt.ask("Public IP address (leave empty to auto-detect)", default=public_ip_default),
            'proxy_mode': Prompt.ask(
                "Installation mode",
                choices=["user", "system"],
                default="user"
            )
        }
        
        if auth_type == "dual":
            config_data['cloudflare_zone_token'] = Prompt.ask(
                "Cloudflare Zone Token (Zone:Read permission)",
                default=env_zone_token,
                password=True if not env_zone_token else False
            )
            config_data['cloudflare_dns_token'] = Prompt.ask(
                "Cloudflare DNS Token (DNS:Edit permission)",
                default=env_dns_token,
                password=True if not env_dns_token else False
            )
        elif auth_type == "token":
            config_data['cloudflare_token'] = Prompt.ask(
                "Cloudflare API Token",
                default=env_token,
                password=True if not env_token else False
            )
        else:
            config_data['cloudflare_api_email'] = Prompt.ask(
                "Cloudflare API Email",
                default=env_email
            )
            config_data['cloudflare_api_key'] = Prompt.ask(
                "Cloudflare Global API Key",
                default=env_key,
                password=True if not env_key else False
            )
        
        config = cls(**config_data)
        
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
