"""
Domain and subdomain utilities for command-line operations
"""
import re
import random
import string


def generate_random_subdomain(length: int = 8) -> str:
    """Generate a random subdomain with the specified length"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def validate_subdomain(subdomain: str) -> bool:
    """Validate that the subdomain has a correct format"""
    # Check that the subdomain contains only allowed characters
    if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', subdomain):
        return False
    return True


def format_fqdn(subdomain: str, domain: str) -> str:
    """Format a fully qualified domain name from subdomain and domain"""
    if not subdomain:
        return domain
    return f"{subdomain}.{domain}" 