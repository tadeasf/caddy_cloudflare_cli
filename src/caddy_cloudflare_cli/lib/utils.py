"""
Utility functions for Caddy Cloudflare CLI
"""
import os
import platform
import logging
import socket
from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Socket utility functions
def is_port_in_use(port: int, host: str = 'localhost') -> bool:
    """Check if a port is already in use on the system"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except socket.error:
            return True

# Alias for backward compatibility
def is_port_available(port, host='localhost'):
    return not is_port_in_use(port)

def find_available_port(start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
    """
    Find an available port in range
    
    Args:
        start_port: Start of port range
        end_port: End of port range
        
    Returns:
        Available port or None if none found
    """
    port = start_port
    while is_port_in_use(port) and port < end_port:
        port += 1
    return port if port <= end_port else None

@lru_cache(maxsize=1)
def get_system_info() -> Tuple[str, str]:
    """
    Get system information
    
    Returns:
        Tuple of (os_type, architecture)
    """
    os_type = platform.system().lower()
    arch = platform.machine().lower()
    
    # Normalize architecture names
    arch_map = {
        'x86_64': 'amd64',
        'amd64': 'amd64',
        'aarch64': 'arm64',
        'arm64': 'arm64',
        'armv7l': 'arm',
        'armv6l': 'arm'
    }
    
    # Normalize OS names
    os_map = {
        'darwin': 'darwin',
        'linux': 'linux',
        'windows': 'windows'
    }
    
    return os_map.get(os_type, os_type), arch_map.get(arch, arch)

def download_file(url: str, target: Path, show_progress: bool = True) -> bool:
    """
    Download file with progress
    
    Args:
        url: URL to download from
        target: Path to save to
        show_progress: Whether to show progress bar
        
    Returns:
        True if successful
    """
    try:
        import requests
        from rich.progress import Progress, DownloadColumn, TransferSpeedColumn
        from requests.exceptions import RequestException

        # Create request with timeout and proper headers
        headers = {
            'User-Agent': 'caddy-cloudflare-cli/1.0'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        response.raise_for_status()
        
        total = int(response.headers.get('content-length', 0))
        
        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'wb') as f:
            if show_progress and total > 0:
                with Progress(
                    "[progress.description]{task.description}",
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                ) as progress:
                    task = progress.add_task(f"Downloading {target.name}", total=total)
                    for data in response.iter_content(chunk_size=8192):
                        size = f.write(data)
                        progress.update(task, advance=size)
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        return True
        
    except RequestException as e:
        logger.error(f"Download failed: {str(e)}")
        if target.exists():
            target.unlink()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        if target.exists():
            target.unlink()
        return False

def ensure_permissions(path: Path, mode: int = 0o755) -> None:
    """
    Ensure file has correct permissions
    
    Args:
        path: Path to file
        mode: Permission mode
    """
    if os.name != 'nt':  # Skip on Windows
        path.chmod(mode)

def normalize_path(path: str) -> str:
    """Normalize file path"""
    return path.replace('\\', '/')

def get_public_ip() -> str:
    """Get the public IP address of the current machine"""
    import requests
    
    # List of services that can return the public IP
    services = [
        "https://api.ipify.org",
        "https://ipinfo.io/ip",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    
    for service in services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                return ip
        except Exception:
            continue
    
    # If all services fail, raise an exception
    raise Exception("Could not determine public IP address")
