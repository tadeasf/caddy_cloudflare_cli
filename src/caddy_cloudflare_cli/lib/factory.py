"""
Factory classes for provider instantiation
"""
from typing import Type, Dict, Optional, Any

from .config import Config
from .dns.base import DNSProvider
from .dns.cloudflare_api_handler import CloudflareDNS
from .proxy.caddy import CaddyProxy

class ProviderFactory:
    """Base factory class for providers"""
    
    @classmethod
    def create(cls, provider_type: str, config: Config):
        """Create provider instance"""
        if provider_type not in cls.get_providers():
            raise ValueError(f"Unsupported provider: {provider_type}")
        return cls.get_providers()[provider_type](config)
    
    @classmethod
    def get_providers(cls) -> Dict[str, Type]:
        """Get available providers"""
        raise NotImplementedError

class DNSProviderFactory(ProviderFactory):
    """Factory for DNS providers"""
    
    _providers = {
        'cloudflare': CloudflareDNS
    }
    
    @classmethod
    def create(cls, provider_type: Optional[str] = None, config: Config = None) -> DNSProvider:
        """
        Create DNS provider instance
        
        Args:
            provider_type: Provider type (if None, uses config.dns_provider)
            config: Configuration object
            
        Returns:
            DNSProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type is None and config is not None:
            provider_type = config.dns_provider
        return super().create(provider_type, config)
    
    @classmethod
    def get_providers(cls) -> Dict[str, Type[DNSProvider]]:
        """Get available DNS providers"""
        return cls._providers
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[DNSProvider]):
        """Register new DNS provider"""
        cls._providers[name] = provider_class

class ProxyProviderFactory(ProviderFactory):
    """Factory for proxy providers"""
    
    _providers = {
        'caddy': CaddyProxy
    }
    
    @classmethod
    def create(cls, provider_type: Optional[str] = None, config: Config = None) -> Any:
        """
        Create proxy provider instance
        
        Args:
            provider_type: Provider type (if None, uses config.proxy_type)
            config: Configuration object
            
        Returns:
            Proxy provider instance (e.g. CaddyProxy)
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type is None and config is not None:
            provider_type = config.proxy_type
        return super().create(provider_type, config)
    
    @classmethod
    def get_providers(cls) -> Dict[str, Type]:
        """Get available proxy providers"""
        return cls._providers
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type):
        """Register new proxy provider"""
        cls._providers[name] = provider_class 