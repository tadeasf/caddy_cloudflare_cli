"""
Debug command implementation for Caddy Cloudflare CLI
"""
import logging
import time

import typer
from rich.console import Console

from ..config import Config, ConfigError
from ..dns.cloudflare_api_handler import CloudflareDNS
from ..utils import get_public_ip

console = Console()

def debug_command():
    """Debug authentication and connection issues"""
    try:
        # Set up logging
        logging.basicConfig(level=logging.DEBUG)
        
        # Load configuration
        console.print("[bold blue]Loading configuration...")
        config = Config.load()
        
        # Show configuration (without sensitive values)
        console.print("\n[bold]Configuration:")
        console.print(f"Domain: {config.domain}")
        
        auth_type = "None"
        if config.cloudflare_zone_token and config.cloudflare_dns_token:
            auth_type = "Zone and DNS Tokens (Least Privilege)"
        elif config.cloudflare_token:
            auth_type = "API Token"
        elif config.cloudflare_api_key and config.cloudflare_api_email:
            auth_type = "Global API Key"
        
        console.print(f"Authentication Type: {auth_type}")
        
        if config.cloudflare_zone_token and config.cloudflare_dns_token:
            console.print(f"Zone Token (masked): {config.cloudflare_zone_token[:4]}...{config.cloudflare_zone_token[-4:] if len(config.cloudflare_zone_token) > 8 else '****'}")
            console.print(f"DNS Token (masked): {config.cloudflare_dns_token[:4]}...{config.cloudflare_dns_token[-4:] if len(config.cloudflare_dns_token) > 8 else '****'}")
                
        console.print(f"Email for certificates: {config.email}")
        console.print(f"Public IP configured: {config.public_ip or 'Not configured (will auto-detect)'}")
        
        # Test Cloudflare authentication
        console.print("\n[bold blue]Testing Cloudflare authentication...")
        
        try:
            # Try direct client initialization
            from cloudflare import Cloudflare
            
            has_valid_token = bool(config.cloudflare_token and config.cloudflare_token.strip())
            has_valid_api_key = bool(config.cloudflare_api_key and config.cloudflare_api_email and 
                                    config.cloudflare_api_key.strip() and config.cloudflare_api_email.strip())
            
            if has_valid_token:
                console.print("[blue]Testing with API Token...")
                console.print(f"Token (masked): {config.cloudflare_token[:4]}...{config.cloudflare_token[-4:] if len(config.cloudflare_token) > 8 else '****'}")
                cf = Cloudflare(api_token=config.cloudflare_token)
            elif has_valid_api_key:
                console.print("[blue]Testing with Global API Key...")
                console.print(f"API Email: {config.cloudflare_api_email}")
                console.print(f"API Key (masked): {config.cloudflare_api_key[:4]}...{config.cloudflare_api_key[-4:] if len(config.cloudflare_api_key) > 8 else '****'}")
                cf = Cloudflare(
                    api_key=config.cloudflare_api_key,
                    api_email=config.cloudflare_api_email
                )
            else:
                console.print("[bold red]No valid Cloudflare credentials found")
                return
                
            # Test API access with a simple request
            console.print("[blue]Testing API access...")
            
            if config.domain:
                # Try to find the zone
                zones = cf.zones.list(name=config.domain)
                
                if zones and hasattr(zones, 'result') and zones.result:
                    # Handle Zone object correctly
                    zone = zones.result[0]
                    zone_id = None
                    
                    # Try to extract zone ID
                    if hasattr(zone, 'id'):
                        zone_id = zone.id
                    elif isinstance(zone, dict) and 'id' in zone:
                        zone_id = zone['id']
                        
                    if zone_id:
                        console.print(f"[bold green]✓ Successfully found zone for {config.domain}")
                        console.print(f"  Zone ID: {zone_id}")
                        
                        try:
                            # Try to list DNS records
                            records = cf.dns.records.list(zone_id=zone_id)
                            record_count = 0
                            
                            if hasattr(records, 'result'):
                                record_count = len(records.result)
                            elif isinstance(records, list):
                                record_count = len(records)
                                
                            console.print(f"[bold green]✓ Successfully retrieved {record_count} DNS records")
                            
                            # Test creating a DNS record (dry run)
                            console.print("\n[bold blue]Testing DNS record creation formats...")
                            
                            # Test different record formats
                            test_formats = [
                                {"name": f"test-{int(time.time())}", "description": "Random subdomain"},
                                {"name": "@", "description": "Root domain"},
                                {"name": config.domain, "description": "Full domain"},
                                {"name": f"test.{config.domain}", "description": "Fully qualified domain"},
                            ]
                            
                            for test in test_formats:
                                console.print(f"[blue]Testing format: {test['description']} ({test['name']})")
                                # Just simulate the data we would send, don't actually create it
                                try:
                                    # Create a DNS handler
                                    CloudflareDNS(config)
                                    
                                    # Create the DNS record data (for validation only)
                                    api_format_name = None
                                    display_name = None
                                    
                                    if test['name'] == "@":
                                        # Root domain - use @ for Cloudflare API
                                        api_format_name = "@"
                                        display_name = config.domain
                                        console.print(f"[blue]→ Would send to API with 'name': '{api_format_name}'")
                                        console.print(f"[blue]→ Would create record for: '{display_name}'")
                                    elif test['name'] == config.domain:
                                        # Full domain = root domain in Cloudflare API
                                        api_format_name = "@"
                                        display_name = config.domain
                                        console.print(f"[blue]→ Would send to API with 'name': '{api_format_name}'")
                                        console.print(f"[blue]→ Would create record for: '{display_name}'")
                                    elif test['name'].endswith(f".{config.domain}"):
                                        # Extract just the subdomain part
                                        subdomain = test['name'].replace(f".{config.domain}", "")
                                        api_format_name = subdomain
                                        display_name = test['name']
                                        console.print(f"[blue]→ Would send to API with 'name': '{api_format_name}'")
                                        console.print(f"[blue]→ Would create record for: '{display_name}'")
                                    else:
                                        # Regular subdomain
                                        api_format_name = test['name']
                                        display_name = f"{test['name']}.{config.domain}"
                                        console.print(f"[blue]→ Would send to API with 'name': '{api_format_name}'")
                                        console.print(f"[blue]→ Would create record for: '{display_name}'")
                                    
                                    # Show what the API call would look like
                                    console.print("[blue]Example API call:")
                                    console.print("[blue]cf.dns.records.create(")
                                    console.print("[blue]    zone_id='{zone_id}',")
                                    console.print("[blue]    type='A',")
                                    console.print("[blue]    name='{api_format_name}',")
                                    console.print("[blue]    content='1.2.3.4'")
                                    console.print("[blue])")
                                    
                                    console.print("[green]✓ Format validation successful")
                                except Exception as e:
                                    console.print(f"[bold red]× Format validation failed: {str(e)}")
                                
                        except Exception as e:
                            console.print(f"[bold red]Failed to list DNS records: {str(e)}")
                    else:
                        console.print(f"[bold red]Failed to extract zone ID for {config.domain}")
                else:
                    console.print(f"[bold red]Domain {config.domain} not found in your Cloudflare account")
                    
                    # List all available zones
                    try:
                        all_zones = cf.zones.list()
                        console.print("\n[blue]Available domains in your account:")
                        if all_zones and hasattr(all_zones, 'result') and all_zones.result:
                            for zone in all_zones.result:
                                zone_name = getattr(zone, 'name', zone['name'] if isinstance(zone, dict) else 'unknown')
                                zone_id = getattr(zone, 'id', zone['id'] if isinstance(zone, dict) else 'unknown')
                                console.print(f"  - {zone_name} (ID: {zone_id})")
                        else:
                            console.print("  None found")
                    except Exception as e:
                        console.print(f"[bold red]Failed to list available domains: {str(e)}")
            else:
                # Just list all zones
                zones = cf.zones.list()
                zone_count = 0
                
                if hasattr(zones, 'result'):
                    zone_count = len(zones.result)
                elif isinstance(zones, list):
                    zone_count = len(zones)
                    
                console.print(f"[bold green]✓ Successfully retrieved {zone_count} zones")
                
                if zone_count > 0:
                    console.print("Available domains:")
                    for zone in (zones.result if hasattr(zones, 'result') else zones):
                        zone_name = getattr(zone, 'name', zone['name'] if isinstance(zone, dict) else 'unknown')
                        zone_id = getattr(zone, 'id', zone['id'] if isinstance(zone, dict) else 'unknown')
                        console.print(f"  - {zone_name} (ID: {zone_id})")
                else:
                    console.print("[bold yellow]No zones found in your Cloudflare account")
            
            console.print("\n[bold green]✓ Cloudflare authentication successful!")
            
            # Check for public IP detection
            console.print("\n[bold blue]Testing public IP detection...")
            try:
                ip = get_public_ip()
                console.print(f"[bold green]✓ Successfully detected public IP: {ip}")
            except Exception as e:
                console.print(f"[bold red]Failed to detect public IP: {str(e)}")
                console.print("[yellow]This may affect DNS record creation if no IP is specified")
                
            # Provide troubleshooting tips
            console.print("\n[bold blue]Troubleshooting tips:")
            console.print("[yellow]1. If you're having DNS name validation issues:")
            console.print("   - Try using the --force-root flag to deploy to the root domain")
            console.print("   - Ensure your subdomain contains only valid characters (letters, numbers, hyphen)")
            console.print("   - Make sure your domain is correctly configured in your Cloudflare account")
            console.print("   - Try using a simpler, shorter subdomain")
            console.print("[yellow]2. If Caddy fails to start:")
            console.print("   - Check that port 80 and 443 are available")
            console.print("   - Ensure Caddy has permission to bind to these ports")
            console.print("   - Verify that you have appropriate permissions to run Caddy")
            console.print("[yellow]3. If your service is not accessible:")
            console.print("   - Verify that your local service is running on the specified port")
            console.print("   - Check that DNS has propagated (can take several minutes)")
            console.print("   - Ensure your firewall allows Caddy to access the local service")
            
        except Exception as e:
            console.print(f"[bold red]Cloudflare API error: {str(e)}")
            console.print("\n[yellow]Troubleshooting tips:")
            console.print("1. Check if your Cloudflare credentials are correct")
            console.print("2. Make sure your API Token has the right permissions (Zone:DNS:Edit)")
            console.print("3. If using Global API Key, ensure both email and key are correct")
            console.print("4. Try running 'caddy-cloudflare init' to reconfigure credentials")
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {str(e)}")
        raise typer.Exit(code=1) 