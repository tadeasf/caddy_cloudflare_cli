"""
Cloudflare DNS handler implementation
"""
import time
import logging
from typing import Dict, List, Optional

import cloudflare
from cloudflare import Cloudflare

from ..config import Config
from .base import DNSProvider, DNSError, DNSRecord

logger = logging.getLogger("caddy_cloudflare_cli.lib.dns.cloudflare_api_handler")

class CloudflareDNS(DNSProvider):
    """Cloudflare DNS provider implementation."""

    def __init__(self, config: Config):
        """Initialize Cloudflare DNS handler"""
        self.config = config
        
        # Initialize Cloudflare client with appropriate auth
        try:
            # Debug auth info
            logger.debug("Cloudflare authentication config:")
            logger.debug(f"  Token: {'Provided' if config.cloudflare_token else 'Not provided'}")
            logger.debug(f"  API Key: {'Provided' if config.cloudflare_api_key else 'Not provided'}")
            logger.debug(f"  Email: {'Provided' if config.cloudflare_api_email else 'Not provided'}")
            
            # Check if token is actually valid/not empty
            has_valid_token = bool(config.cloudflare_token and config.cloudflare_token.strip())
            has_valid_api_key = bool(config.cloudflare_api_key and config.cloudflare_api_email and 
                                    config.cloudflare_api_key.strip() and config.cloudflare_api_email.strip())
            
            if has_valid_token:
                # Use API Token authentication (preferred method)
                logger.info("Using API Token authentication")
                self.cf = Cloudflare(api_token=config.cloudflare_token)
            elif has_valid_api_key:
                # Use Global API Key authentication (legacy method)
                logger.info("Using Global API Key authentication")
                logger.info(f"Email: {config.cloudflare_api_email}")
                self.cf = Cloudflare(
                    api_key=config.cloudflare_api_key,
                    api_email=config.cloudflare_api_email
                )
            else:
                raise DNSError("No valid Cloudflare credentials provided. Please set CLOUDFLARE_API_KEY and CLOUDFLARE_EMAIL in your .env file or configure via 'caddy-cloudflare init'")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare client: {str(e)}", exc_info=True)
            raise DNSError(f"Failed to initialize Cloudflare client: {str(e)}")
        self._zone_id = None

    @property
    def zone_id(self) -> str:
        """Get zone ID for domain"""
        if not self._zone_id:
            try:
                # Use list method with name filter instead of get method
                zones = self.cf.zones.list(name=self.config.domain)
                # Check if we have any results
                if not zones or not hasattr(zones, 'result') or not zones.result:
                    raise DNSError(f"Domain {self.config.domain} not found in your Cloudflare account")
                
                # Handle the Zone object correctly - it's now an object, not a dictionary
                zone = zones.result[0]
                # The id is now an attribute of Zone object
                if hasattr(zone, 'id'):
                    self._zone_id = zone.id
                else:
                    # Fallback attempt for backward compatibility
                    self._zone_id = zone['id'] if isinstance(zone, dict) else None
                    
                if not self._zone_id:
                    raise DNSError(f"Could not extract zone ID for domain {self.config.domain}")
            except Exception as e:
                raise DNSError(f"Cloudflare API error: {str(e)}")
        return self._zone_id

    def create_record(
        self,
        subdomain: Optional[str] = None,
        content: Optional[str] = None,
        record_type: str = "A",
        proxied: bool = True,
        ttl: int = 1,
        force_update: bool = False
    ) -> DNSRecord:
        """
        Create a DNS record for the specified subdomain.
        
        Args:
            subdomain: The subdomain to create the record for
            content: The content of the record (e.g. IP address for A records)
            record_type: The type of record (A, CNAME, etc.)
            proxied: Whether the record should be proxied through Cloudflare
            ttl: Time to live in seconds (1 means automatic)
            force_update: Whether to update the record if it already exists
            
        Returns:
            The created DNS record
        """
        try:
            # Determine IP to use (either provided, from config, or auto-detected)
            if content is None:
                if self.config.public_ip:
                    content = self.config.public_ip
                    logger.info(f"Using configured public IP: {content}")
                else:
                    from caddy_cloudflare_cli.lib.utils import get_public_ip
                    content = get_public_ip()
                    logger.info(f"Auto-detected public IP: {content}")

            # Get the zone ID for the domain
            zone_id = self.zone_id
            
            # Format the subdomain correctly for Cloudflare's API
            # Always use the subdomain as provided
            record_name = subdomain
            display_name = f"{subdomain}.{self.config.domain}"
                
            logger.info(f"Creating DNS record: {display_name} with content {content}")
            
            # Prepare data for API request
            data = {
                "type": record_type,
                "name": record_name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl
            }
            
            logger.debug(f"API request data: {data}")
            logger.debug("Attempting to create DNS record with Cloudflare API")
            
            # Check if record exists already and we need to update it
            if force_update:
                existing_records = self.list_dns_records(type=record_type, name=record_name)
                if existing_records:
                    # Update existing record
                    existing_record = existing_records[0]
                    logger.info(f"Updating existing DNS record {existing_record.id} for {display_name}")
                    
                    try:
                        response = self.cf.dns.records.update(
                            zone_id=zone_id,
                            dns_record_id=existing_record.id,
                            type=record_type,
                            name=record_name,
                            content=content,
                            proxied=proxied,
                            ttl=ttl
                        )
                        return self._record_to_dns_record(response.result if hasattr(response, 'result') else response)
                    except Exception as update_error:
                        logger.error(f"Failed to update existing record: {str(update_error)}")
                        # Fall through to create attempt
            
            # If we're here, either there's no existing record or update failed
            try:
                response = self.cf.dns.records.create(
                    zone_id=zone_id,
                    type=record_type,
                    name=record_name,
                    content=content,
                    proxied=proxied,
                    ttl=ttl
                )
                return self._record_to_dns_record(response.result if hasattr(response, 'result') else response)
            except cloudflare.BadRequestError as e:
                error_msg = str(e)
                logger.error(f"Cloudflare API error: {error_msg}")
                
                if "already exists" in error_msg.lower():
                    logger.warning("Record already exists. Use force_update=True to update it.")
                    raise DNSError(f"DNS record {display_name} already exists. Use --force-update to update it.")
                elif "DNS name is invalid" in error_msg:
                    # Provide helpful error for invalid DNS names
                    raise DNSError(f"DNS name '{display_name}' is invalid. Ensure your subdomain contains only letters, numbers, and hyphens.")
                else:
                    # Pass through other errors
                    raise DNSError(f"Failed to create DNS record: {error_msg}")
            except Exception as e:
                logger.error(f"Failed to create DNS record: {str(e)}", exc_info=True)
                raise DNSError(f"Failed to create DNS record: {str(e)}")
        except DNSError:
            # Re-raise DNS errors without modification
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating DNS record: {str(e)}", exc_info=True)
            raise DNSError(f"Unexpected error creating DNS record: {str(e)}")

    def delete_record(self, record_id: str) -> bool:
        """Delete DNS record"""
        try:
            self.cf.dns.records.delete(zone_id=self.zone_id, identifier=record_id)
            return True
        except Exception as e:
            raise DNSError(f"Failed to delete DNS record: {str(e)}")

    def get_record(self, record_id: str) -> Optional[DNSRecord]:
        """Get DNS record by ID"""
        try:
            record = self.cf.dns.records.get(zone_id=self.zone_id, identifier=record_id)
            if hasattr(record, 'result'):
                return self._record_to_dns_record(record.result)
            else:
                # Direct response without result wrapper
                return self._record_to_dns_record(record)
        except Exception as e:
            logger.warning(f"Failed to get DNS record {record_id}: {str(e)}")
            return None

    def list_records(self, record_type: Optional[str] = None) -> List[DNSRecord]:
        """List DNS records"""
        try:
            # Handle both API styles
            try:
                if record_type:
                    # Try new API style
                    records = self.cf.dns.records.list(zone_id=self.zone_id, type=record_type)
                else:
                    records = self.cf.dns.records.list(zone_id=self.zone_id)
            except TypeError:
                # Fallback to old API style with params
                logger.debug("Falling back to older API format with params")
                params = {}
                if record_type:
                    params["type"] = record_type
                records = self.cf.dns.records.list(zone_id=self.zone_id, params=params)
            
            if hasattr(records, 'result'):
                return [self._record_to_dns_record(r) for r in records.result]
            else:
                # Handle case where records might already be a list
                if isinstance(records, list):
                    return [self._record_to_dns_record(r) for r in records]
                # Handle empty or null response
                return []
        except Exception as e:
            logger.error(f"Failed to list DNS records: {str(e)}", exc_info=True)
            raise DNSError(f"Failed to list DNS records: {str(e)}")

    def list_dns_records(self, name=None, type=None, content=None) -> List[DNSRecord]:
        """
        List DNS records with optional filtering.
        
        Args:
            name: Filter by record name
            type: Filter by record type
            content: Filter by record content
            
        Returns:
            List of DNSRecord objects
        """
        try:
            zone_id = self.zone_id
            
            # Build parameters for the API request
            params = {}
            if name is not None:
                params["name"] = name
            if type is not None:
                params["type"] = type
            if content is not None:
                params["content"] = content
                
            logger.debug(f"Fetching DNS records with params: {params}")
            
            # Fetch records from Cloudflare API
            response = self.cf.dns.records.get(zone_id, params=params)
            
            # Convert to DNSRecord objects
            records = []
            for record in response.result:
                try:
                    dns_record = self._record_to_dns_record(record)
                    records.append(dns_record)
                except Exception as record_error:
                    logger.warning(f"Failed to process record {record}: {str(record_error)}")
                    
            logger.info(f"Found {len(records)} DNS records matching filters")
            return records
            
        except Exception as e:
            logger.error(f"Failed to list DNS records: {str(e)}")
            return []

    def _record_to_dns_record(self, record: Dict) -> DNSRecord:
        """Convert Cloudflare record to DNSRecord"""
        try:
            # Handle record as object or dictionary
            if hasattr(record, 'id'):
                # Handle as object with attributes
                return DNSRecord(
                    id=record.id,
                    name=record.name,
                    type=record.type,
                    content=record.content,
                    proxied=getattr(record, 'proxied', False),
                    ttl=getattr(record, 'ttl', 1)
                )
            else:
                # Handle as dictionary (backward compatibility)
                return DNSRecord(
                    id=record['id'],
                    name=record['name'],
                    type=record['type'],
                    content=record['content'],
                    proxied=record.get('proxied', False),
                    ttl=record.get('ttl', 1)
                )
        except Exception as e:
            logger.error(f"Error converting record to DNSRecord: {str(e)}", exc_info=True)
            # Create minimal record if possible to avoid crashing
            return DNSRecord(
                id=getattr(record, 'id', record['id'] if isinstance(record, dict) else 'unknown'),
                name=getattr(record, 'name', record['name'] if isinstance(record, dict) else 'unknown'),
                type=getattr(record, 'type', record['type'] if isinstance(record, dict) else 'unknown'),
                content=getattr(record, 'content', record['content'] if isinstance(record, dict) else 'unknown'),
                proxied=False,
                ttl=1
            )

    def verify_propagation(self, record: DNSRecord, timeout: int = 60) -> bool:
        """Verify DNS record propagation"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                current = self.get_record(record.id)
                if current and current.content == record.content:
                    logger.info(f"DNS record {record.name} propagated successfully")
                    return True
                logger.debug("DNS record not yet propagated, waiting...")
                time.sleep(5)
            except Exception as e:
                logger.warning(f"Error verifying propagation: {str(e)}")
                time.sleep(5)
        logger.warning(f"DNS record propagation timed out after {timeout} seconds")
        return False

    def update_record(
        self,
        record_id: str,
        subdomain: Optional[str] = None,
        content: Optional[str] = None,
        record_type: str = "A",
        proxied: bool = True,
        ttl: int = 1
    ) -> DNSRecord:
        """
        Update an existing DNS record.
        
        Args:
            record_id: ID of the record to update
            subdomain: The subdomain to update
            content: The content of the record (e.g. IP address for A records)
            record_type: The type of record (A, CNAME, etc.)
            proxied: Whether the record should be proxied through Cloudflare
            ttl: Time to live in seconds (1 means automatic)
            
        Returns:
            The updated DNS record
        """
        try:
            # Get the zone ID for the domain
            zone_id = self.zone_id
            
            # Determine the record name (subdomain)
            record_name = subdomain
            
            # Prepare data for API request
            data = {
                "type": record_type,
                "name": record_name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl
            }
            
            logger.debug(f"Updating DNS record {record_id} with data: {data}")
            
            # Make the API request
            response = self.cf.dns.records.update(
                zone_id=zone_id,
                dns_record_id=record_id,
                **data
            )
            
            # Convert response to DNSRecord object
            return self._record_to_dns_record(response.result if hasattr(response, 'result') else response)
        except Exception as e:
            logger.error(f"Failed to update DNS record: {str(e)}", exc_info=True)
            raise DNSError(f"Failed to update DNS record: {str(e)}") 