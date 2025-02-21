"""
Cloudflare DNS provider implementation
"""
import time
from typing import Dict, Optional, List
import CloudFlare

from ..config import Config
from .base import DNSProvider, DNSRecord, DNSError

class CloudflareDNS(DNSProvider):
    """Cloudflare DNS provider implementation"""
    
    def __init__(self, config: Config):
        """
        Initialize Cloudflare DNS provider
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.cf = CloudFlare.CloudFlare(token=config.cloudflare_token)
        self._zone_id = None
    
    @property
    def zone_id(self) -> str:
        """Get zone ID for configured domain"""
        if self._zone_id is None:
            try:
                zones = self.cf.zones.get(params={'name': self.config.domain})
                if not zones:
                    raise DNSError(f"Domain {self.config.domain} not found in your Cloudflare account")
                self._zone_id = zones[0]['id']
            except CloudFlare.exceptions.CloudFlareAPIError as e:
                raise DNSError(f"Cloudflare API error: {str(e)}")
        return self._zone_id
    
    def _record_to_dns_record(self, cf_record: Dict) -> DNSRecord:
        """Convert Cloudflare record to DNSRecord"""
        return DNSRecord(
            id=cf_record['id'],
            name=cf_record['name'],
            type=cf_record['type'],
            content=cf_record['content'],
            proxied=cf_record.get('proxied', False),
            ttl=cf_record.get('ttl', 1)
        )
    
    def create_record(self, subdomain: str, record_type: str = "A", 
                     content: str = "127.0.0.1", proxied: bool = True,
                     ttl: int = 1) -> DNSRecord:
        """Create a DNS record"""
        try:
            # Full domain name
            name = f"{subdomain}.{self.config.domain}"
            
            # Check if record exists
            existing = self.cf.zones.dns_records.get(
                self.zone_id,
                params={'name': name, 'type': record_type}
            )
            if existing:
                raise DNSError(f"DNS record for {name} already exists")
            
            # Create record
            record = {
                'name': name,
                'type': record_type,
                'content': content,
                'proxied': proxied,
                'ttl': ttl
            }
            
            result = self.cf.zones.dns_records.post(self.zone_id, data=record)
            
            # Wait for propagation
            dns_record = self._record_to_dns_record(result)
            if not self.verify_propagation(dns_record):
                self.delete_record(dns_record.id)
                raise DNSError(f"DNS record {name} failed to propagate")
            
            return dns_record
            
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            raise DNSError(f"Failed to create DNS record: {str(e)}")
    
    def delete_record(self, record_id: str) -> bool:
        """Delete a DNS record"""
        try:
            self.cf.zones.dns_records.delete(self.zone_id, record_id)
            return True
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            raise DNSError(f"Failed to delete DNS record: {str(e)}")
    
    def get_record(self, record_id: str) -> Optional[DNSRecord]:
        """Get a DNS record by ID"""
        try:
            record = self.cf.zones.dns_records.get(self.zone_id, record_id)
            return self._record_to_dns_record(record)
        except CloudFlare.exceptions.CloudFlareAPIError:
            return None
    
    def list_records(self, record_type: Optional[str] = None) -> List[DNSRecord]:
        """List DNS records"""
        try:
            params = {'type': record_type} if record_type else {}
            records = self.cf.zones.dns_records.get(self.zone_id, params=params)
            return [self._record_to_dns_record(r) for r in records]
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            raise DNSError(f"Failed to list DNS records: {str(e)}")
    
    def verify_propagation(self, record: DNSRecord, timeout: int = 60) -> bool:
        """Verify DNS record has propagated"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                current = self.get_record(record.id)
                if current and current.content == record.content:
                    return True
            except Exception:
                pass
            time.sleep(5)  # Wait between checks
        
        raise TimeoutError(f"Timeout waiting for DNS record {record.name} to propagate") 