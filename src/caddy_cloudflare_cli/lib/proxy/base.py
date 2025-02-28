"""
Base class for reverse proxy servers
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path

@dataclass
class ProxyConfig:
    """Proxy configuration data"""
    domain: str
    target: str
    ssl: bool = True
    additional_config: Dict = None

@dataclass
class ProxyStatus:
    """Proxy server status"""
    running: bool
    pid: Optional[int]
    config_file: Optional[Path]
    error: Optional[str]

class ReverseProxy(ABC):
    """Abstract base class for reverse proxy servers"""
    
    @abstractmethod
    def generate_config(self, config: ProxyConfig) -> str:
        """
        Generate proxy configuration
        
        Args:
            config: ProxyConfig object
            
        Returns:
            Configuration string
            
        Raises:
            ProxyError: If configuration generation fails
        """
        pass
    
    @abstractmethod
    def validate_config(self, config_str: str) -> bool:
        """
        Validate configuration
        
        Args:
            config_str: Configuration to validate
            
        Returns:
            True if configuration is valid
            
        Raises:
            ProxyError: If validation fails
        """
        pass
    
    @abstractmethod
    def start(self, config_file: Path) -> ProxyStatus:
        """
        Start the proxy server
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            ProxyStatus object
            
        Raises:
            ProxyError: If server fails to start
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """
        Stop the proxy server
        
        Returns:
            True if successful
            
        Raises:
            ProxyError: If server fails to stop
        """
        pass
    
    @abstractmethod
    def reload(self) -> bool:
        """
        Reload configuration
        
        Returns:
            True if successful
            
        Raises:
            ProxyError: If reload fails
        """
        pass
    
    @abstractmethod
    def status(self) -> ProxyStatus:
        """
        Get proxy server status
        
        Returns:
            ProxyStatus object
        """
        pass
    
    @abstractmethod
    def install(self, system_wide: bool = False) -> bool:
        """
        Install proxy server
        
        Args:
            system_wide: Whether to install system-wide
            
        Returns:
            True if successful
            
        Raises:
            ProxyError: If installation fails
        """
        pass
    
    @abstractmethod
    def uninstall(self) -> bool:
        """
        Uninstall proxy server
        
        Returns:
            True if successful
            
        Raises:
            ProxyError: If uninstallation fails
        """
        pass

class ProxyError(Exception):
    """Base exception for proxy operations"""
    pass 