"""
Port management utilities for command-line operations
"""
import socket
from typing import List

# Default common developer ports
DEFAULT_PORTS = [8080, 3000, 5000, 8000, 9000]


def validate_port(port: int) -> bool:
    """Validate port number is in valid range"""
    return 1 <= port <= 65535


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use on the system"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except socket.error:
            return True


def suggest_available_port(start_port: int = 8080) -> int:
    """Find an available port starting from the given port"""
    port = start_port
    while is_port_in_use(port) and port < 65535:
        port += 1
    return port


def get_port_status(ports: List[int]) -> dict:
    """Get status (available/in use) for a list of ports"""
    return {port: ("available" if not is_port_in_use(port) else "in use") for port in ports} 