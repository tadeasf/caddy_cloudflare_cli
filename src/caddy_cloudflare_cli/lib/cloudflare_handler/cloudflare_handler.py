"""
Cloudflare API management for Caddy Cloudflare CLI
"""
import time
from typing import Dict, Optional

from cloudflare import Cloudflare, APIError

from ..config import Config
from ..utils import generate_random_subdomain

class CloudflareManager:
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize Cloudflare client with appropriate auth
        if config.cloudflare_token:
            # Use API Token authentication (preferred method)
            self.cf = Cloudflare(api_token=config.cloudflare_token)
        elif config.cloudflare_api_key and config.cloudflare_api_email:
            # Use Global API Key authentication (legacy method)
            self.cf = Cloudflare(
                api_key=config.cloudflare_api_key,
                api_email=config.cloudflare_api_email
            )
        else:
            raise Exception("No valid Cloudflare credentials provided")
            
        self._zone_id = None

    @property
    def zone_id(self) -> str:
        """Get zone ID for the configured domain"""
        if self._zone_id is None:
            try:
                zones = self.cf.zones.list(name=self.config.domain)
                if not zones or not zones.result:
                    raise Exception(f"Domain {self.config.domain} not found in your Cloudflare account")
                self._zone_id = zones.result[0]['id']
            except APIError as e:
                raise Exception(f"Cloudflare API error: {str(e)}")
        return self._zone_id

    def create_record(self, subdomain: Optional[str] = None) -> Dict:
        """Create an A record for the subdomain"""
        if not subdomain:
            subdomain = generate_random_subdomain()

        # Full domain name
        name = f"{subdomain}.{self.config.domain}"

        try:
            # Check if record already exists
            existing = self.cf.dns.records.list(
                zone_id=self.zone_id,
                params={"name": name, "type": "A"}
            )
            
            if existing and existing.result:
                raise Exception(f"DNS record for {name} already exists")

            # Create new A record pointing to localhost
            result = self.cf.dns.records.create(
                zone_id=self.zone_id,
                data={
                    "name": name,
                    "type": "A",
                    "content": "127.0.0.1",  # Local machine
                    "proxied": True  # Enable Cloudflare proxy
                }
            )
            
            # Wait for DNS propagation
            self._wait_for_propagation(name)
            
            return result.result
        except APIError as e:
            raise Exception(f"Cloudflare API error: {str(e)}")

    def _wait_for_propagation(self, name: str, timeout: int = 60, interval: int = 5):
        """Wait for DNS record to propagate"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                records = self.cf.dns.records.list(
                    zone_id=self.zone_id,
                    params={"name": name, "type": "A"}
                )
                if records and records.result and records.result[0]['name'] == name:
                    return True
            except Exception:
                pass
            time.sleep(interval)
        
        raise Exception(f"Timeout waiting for DNS propagation of {name}")
