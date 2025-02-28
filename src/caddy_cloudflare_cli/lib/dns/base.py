"""
Base class for DNS providers
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class DNSRecord:
    """DNS record data"""
    id: str
    name: str
    type: str
    content: str
    proxied: bool
    ttl: int

class DNSProvider(ABC):
    """Abstract base class for DNS providers"""
    
    @abstractmethod
    def create_record(self, subdomain: str, record_type: str = "A", content: str = "127.0.0.1",
                     proxied: bool = True, ttl: int = 1) -> DNSRecord:
        """
        Create a DNS record
        
        Args:
            subdomain: Subdomain to create
            record_type: DNS record type (A, CNAME, etc.)
            content: Record content (IP or domain)
            proxied: Whether to proxy through provider's network
            ttl: Time to live in seconds
            
        Returns:
            DNSRecord object
            
        Raises:
            DNSError: If record creation fails
        """
        pass
    
    @abstractmethod
    def delete_record(self, record_id: str) -> bool:
        """
        Delete a DNS record
        
        Args:
            record_id: ID of record to delete
            
        Returns:
            True if successful
            
        Raises:
            DNSError: If record deletion fails
        """
        pass
    
    @abstractmethod
    def get_record(self, record_id: str) -> Optional[DNSRecord]:
        """
        Get a DNS record by ID
        
        Args:
            record_id: ID of record to retrieve
            
        Returns:
            DNSRecord if found, None otherwise
        """
        pass
    
    @abstractmethod
    def list_records(self, record_type: Optional[str] = None) -> List[DNSRecord]:
        """
        List DNS records
        
        Args:
            record_type: Optional filter by record type
            
        Returns:
            List of DNSRecord objects
        """
        pass
    
    @abstractmethod
    def verify_propagation(self, record: DNSRecord, timeout: int = 60) -> bool:
        """
        Verify DNS record has propagated
        
        Args:
            record: Record to verify
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if record has propagated
            
        Raises:
            TimeoutError: If verification times out
        """
        pass

class DNSError(Exception):
    """Base exception for DNS operations"""
    pass 