"""
Cloudflare API management for Caddy Cloudflare CLI
"""
import time
from typing import Dict, Optional

import CloudFlare

from .lib.config import Config
from .lib.utils import generate_random_subdomain

class CloudflareManager:
    def __init__(self, config: Config):
        self.config = config
        self.cf = CloudFlare.CloudFlare(token=config.cloudflare_token)
        self._zone_id = None

    @property
    def zone_id(self) -> str:
        """Get zone ID for the configured domain"""
        if self._zone_id is None:
            zones = self.cf.zones.get(params={'name': self.config.domain})
            if not zones:
                raise Exception(f"Domain {self.config.domain} not found in your Cloudflare account")
            self._zone_id = zones[0]['id']
        return self._zone_id

    def create_record(self, subdomain: Optional[str] = None) -> Dict:
        """Create an A record for the subdomain"""
        if not subdomain:
            subdomain = generate_random_subdomain()

        # Full domain name
        name = f"{subdomain}.{self.config.domain}"

        # Check if record already exists
        existing = self.cf.zones.dns_records.get(
            self.zone_id,
            params={'name': name, 'type': 'A'}
        )
        
        if existing:
            raise Exception(f"DNS record for {name} already exists")

        # Create new A record pointing to localhost
        record = {
            'name': name,
            'type': 'A',
            'content': '127.0.0.1',  # Local machine
            'proxied': True  # Enable Cloudflare proxy
        }

        result = self.cf.zones.dns_records.post(self.zone_id, data=record)
        
        # Wait for DNS propagation
        self._wait_for_propagation(name)
        
        return result

    def _wait_for_propagation(self, name: str, timeout: int = 60, interval: int = 5):
        """Wait for DNS record to propagate"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                records = self.cf.zones.dns_records.get(
                    self.zone_id,
                    params={'name': name, 'type': 'A'}
                )
                if records and records[0]['name'] == name:
                    return True
            except Exception:
                pass
            time.sleep(interval)
        
        raise Exception(f"Timeout waiting for DNS propagation of {name}")
