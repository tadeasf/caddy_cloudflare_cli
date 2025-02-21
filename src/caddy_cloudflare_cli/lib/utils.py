"""
Utility functions for Caddy Cloudflare CLI
"""
import os
import re
import random
import string
import socket
import requests
import platform
from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache

def validate_subdomain(subdomain: str) -> bool:
    """
    Validate subdomain format
    
    Args:
        subdomain: Subdomain to validate
        
    Returns:
        True if valid
    """
    if not subdomain:
        return True
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    return bool(re.match(pattern, subdomain))

def validate_port(port: int) -> bool:
    """
    Validate port number
    
    Args:
        port: Port number to validate
        
    Returns:
        True if valid
    """
    return isinstance(port, int) and 1 <= port <= 65535

def generate_random_subdomain(length: int = 8) -> str:
    """
    Generate a random subdomain
    
    Args:
        length: Length of subdomain
        
    Returns:
        Random subdomain string
    """
    chars = string.ascii_lowercase + string.digits
    while True:
        subdomain = ''.join(random.choice(chars) for _ in range(length))
        if validate_subdomain(subdomain):
            return subdomain

def is_port_available(port: int, host: str = 'localhost') -> bool:
    """
    Check if port is available
    
    Args:
        port: Port to check
        host: Host to check
        
    Returns:
        True if port is available
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
        return True
    except OSError:
        return False

def find_available_port(start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
    """
    Find an available port in range
    
    Args:
        start_port: Start of port range
        end_port: End of port range
        
    Returns:
        Available port or None if none found
    """
    for port in range(start_port, end_port + 1):
        if is_port_available(port):
            return port
    return None

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
        'arm64': 'arm64'
    }
    
    return os_type, arch_map.get(arch, arch)

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
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total = int(response.headers.get('content-length', 0))
        
        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'wb') as f:
            if show_progress:
                from rich.progress import Progress
                with Progress() as progress:
                    task = progress.add_task("[cyan]Downloading...", total=total)
                    for data in response.iter_content(chunk_size=8192):
                        f.write(data)
                        progress.update(task, advance=len(data))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        return True
    except Exception:
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
