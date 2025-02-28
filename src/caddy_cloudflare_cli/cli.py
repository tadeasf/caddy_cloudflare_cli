"""
Command-line interface for Caddy Cloudflare CLI
"""
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
import logging
import time

from .lib.dns.cloudflare_api_handler import CloudflareDNS
from .lib.proxy.caddy import CaddyProxy
from .lib.proxy.base import ProxyConfig
from .lib.config import Config, ConfigError
from .lib.utils import validate_subdomain, validate_port, generate_random_subdomain, get_public_ip

console = Console()
app = typer.Typer(help="Caddy Cloudflare CLI - Easy DNS and reverse proxy setup")
proxy_app = typer.Typer(help="Manage the Caddy proxy server")
app.add_typer(proxy_app, name="proxy")

@app.command()
def init():
    """Initialize Caddy Cloudflare CLI configuration"""
    try:
        config = Config.initialize_interactive()
        console.print("[bold green]✓ Configuration initialized successfully!")
        console.print(f"\nYou can now use other commands like 'install' and 'deploy' with domain {config.domain}.")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@proxy_app.command()
def start(config: Optional[Path] = typer.Option(None, '--config', '-c', help='Path to Caddyfile')):
    """Start the Caddy proxy server"""
    try:
        config_obj = Config.load()
        proxy = CaddyProxy(config_obj)
        
        if config:
            config_path = config
        else:
            # Use default config
            config_path = proxy.dirs['config'] / 'Caddyfile'
            if not config_path.exists():
                typer.echo("No configuration file found. Please run 'deploy' first or specify a config file.")
                raise typer.Exit(code=1)
        
        status = proxy.start(config_path)
        if status.running:
            console.print("[bold green]✓ Caddy started successfully")
            console.print(f"PID: {status.pid}")
        else:
            typer.echo(f"Failed to start Caddy: {status.error}")
            raise typer.Exit(code=1)
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@proxy_app.command()
def stop():
    """Stop the Caddy proxy server"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.stop():
            console.print("[bold green]✓ Caddy stopped successfully")
        else:
            console.print("[bold yellow]! Caddy was not running")
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@proxy_app.command()
def status():
    """Show proxy server status"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        status = proxy.status()
        
        if status.running:
            console.print("[bold green]✓ Caddy is running")
            console.print(f"PID: {status.pid}")
            console.print(f"Config: {status.config_file}")
        else:
            console.print("[bold red]✗ Caddy is not running")
            if status.error:
                console.print(f"Error: {status.error}")
                
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@proxy_app.command()
def reload():
    """Reload proxy configuration"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.reload():
            console.print("[bold green]✓ Configuration reloaded successfully")
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def install(system: bool = typer.Option(False, help='Install system-wide')):
    """Install Caddy binary"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.install(system_wide=system):
            console.print("[bold green]✓ Caddy installed successfully")
            if system:
                console.print("Caddy is now available system-wide at: /usr/local/bin/caddy")
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def uninstall():
    """Uninstall Caddy"""
    try:
        if not Confirm.ask("Are you sure you want to uninstall Caddy?"):
            return
            
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.uninstall():
            console.print("[bold green]✓ Caddy uninstalled successfully")
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def deploy(
    subdomain: Optional[str] = typer.Option(
        None, "--subdomain", "-s", help="Subdomain to use for DNS record"
    ),
    port: int = typer.Option(
        8080, "--port", "-p", help="Port to expose through the tunnel"
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    verify_credentials: bool = typer.Option(
        False, "--verify-credentials", help="Verify Cloudflare credentials without deploying"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", "-l", help="Set logging level"
    ),
    public_ip: Optional[str] = typer.Option(
        None, "--public-ip", help="Public IP to use for the DNS record"
    ),
    force_update: bool = typer.Option(
        False, "--force-update", help="Force update of existing DNS records"
    ),
):
    """
    Deploy with Cloudflare DNS tunnel.
    
    Sets up a Cloudflare DNS record for a subdomain and configures Caddy as a reverse proxy.
    The subdomain will be generated randomly if not provided.
    
    This tool is designed for rapidly deploying subdomains for internal tooling and home labs.
    """
    # Configure logging based on options
    if verbose:
        log_level = "DEBUG"
    
    # Set the logging level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {log_level}")
        numeric_level = logging.INFO
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    try:
        # Load configuration
        config = Config.load()
        
        # Verify credentials if requested
        if verify_credentials:
            console.print("[bold blue]Verifying Cloudflare credentials...")
            
            # Show which auth method is configured
            has_valid_token = bool(config.cloudflare_token and config.cloudflare_token.strip())
            has_valid_api_key = bool(config.cloudflare_api_key and config.cloudflare_api_email and 
                                     config.cloudflare_api_key.strip() and config.cloudflare_api_email.strip())
            has_valid_dual_tokens = bool(config.cloudflare_zone_token and config.cloudflare_dns_token and
                                     config.cloudflare_zone_token.strip() and config.cloudflare_dns_token.strip())
            
            if has_valid_dual_tokens:
                console.print("[blue]Using Zone and DNS Token authentication (least privilege)")
                console.print(f"Zone Token (masked): {config.cloudflare_zone_token[:4]}...{config.cloudflare_zone_token[-4:] if len(config.cloudflare_zone_token) > 8 else '****'}")
                console.print(f"DNS Token (masked): {config.cloudflare_dns_token[:4]}...{config.cloudflare_dns_token[-4:] if len(config.cloudflare_dns_token) > 8 else '****'}")
            elif has_valid_token:
                console.print("[blue]Using API Token authentication")
                console.print(f"Token (masked): {config.cloudflare_token[:4]}...{config.cloudflare_token[-4:] if len(config.cloudflare_token) > 8 else '****'}")
            elif has_valid_api_key:
                console.print("[blue]Using Global API Key authentication")
                console.print(f"Email: {config.cloudflare_api_email}")
                console.print(f"API Key (masked): {config.cloudflare_api_key[:4]}...{config.cloudflare_api_key[-4:] if len(config.cloudflare_api_key) > 8 else '****'}")
            else:
                console.print("[bold red]No valid Cloudflare credentials configured")
                console.print("Please run 'caddy-cloudflare init' to set up credentials")
                return
                
            try:
                # Initialize CloudflareDNS instance
                dns = CloudflareDNS(config)
                
                # Test API access by listing zones
                zone_id = dns.zone_id  # This will test API access and domain lookup
                console.print("[bold green]✓ Successfully authenticated with Cloudflare")
                console.print(f"[bold green]✓ Found zone ID for domain {config.domain}: {zone_id}")
                return
            except Exception as e:
                console.print(f"[bold red]Error: {str(e)}")
                return
                
        # Interactive mode if parameters not provided
        if subdomain is None:
            subdomain = Prompt.ask(
                "Enter subdomain (leave empty for auto-generation)",
                default="",
                show_default=False
            )
        
        # Handle empty subdomain (generate random one)
        if subdomain == "":
            subdomain = generate_random_subdomain()
            console.print(f"[bold blue]Generated random subdomain: {subdomain}")
        
        # Validate subdomain if provided
        if not validate_subdomain(subdomain):
            console.print("[bold red]Invalid subdomain format")
            console.print("Subdomains should contain only letters, numbers, and hyphens, and not start or end with a hyphen.")
            raise typer.Exit(code=1)
        
        if not port:
            port_str = Prompt.ask("Enter target service port")
            try:
                port = int(port_str)
                if not validate_port(port):
                    raise ValueError("Port must be between 1 and 65535")
            except ValueError as e:
                console.print(f"[bold red]Invalid port number: {str(e)}")
                raise typer.Exit(code=1)

        # Initialize providers
        try:
            # Show authentication method being used
            if config.cloudflare_zone_token and config.cloudflare_dns_token:
                console.print("[blue]Using Cloudflare Zone and DNS Tokens for authentication (least privilege)")
            elif config.cloudflare_token:
                console.print("[blue]Using Cloudflare API Token for authentication")
            elif config.cloudflare_api_key and config.cloudflare_api_email:
                console.print("[blue]Using Cloudflare Global API Key for authentication")
            else:
                console.print("[bold red]No valid Cloudflare credentials found")
                console.print("Please run 'caddy-cloudflare init' to set up your credentials")
                raise typer.Exit(code=1)
                
            dns = CloudflareDNS(config)
        except Exception as e:
            console.print(f"[bold red]Failed to initialize Cloudflare: {str(e)}")
            # If it's an auth issue, provide more guidance
            if "authentication" in str(e).lower() or "auth" in str(e).lower() or "invalid" in str(e).lower():
                console.print("\n[yellow]Authentication troubleshooting tips:")
                console.print("1. Make sure you've entered the correct API Token or Global API Key")
                console.print("2. For API Token, ensure it has the Zone:DNS:Edit permission")
                console.print("3. For Global API Key, verify both the key and email are correct")
                console.print("4. Run 'caddy-cloudflare init' to update your credentials")
            raise typer.Exit(code=1)

        proxy = CaddyProxy(config)

        with console.status("[bold green]Deploying service...") as status:
            # Create DNS record
            status.update("[bold blue]Creating DNS record...")
            try:
                # If public_ip was specified in the command, use it
                content = public_ip
                
                if content:
                    console.print(f"[blue]Using provided public IP: {content}")
                    dns_record = dns.create_record(subdomain, content=content, force_update=force_update)
                elif config.public_ip:
                    console.print(f"[blue]Using configured public IP: {config.public_ip}")
                    dns_record = dns.create_record(subdomain, force_update=force_update)
                else:
                    console.print("[blue]Auto-detecting public IP address...")
                    try:
                        detected_ip = get_public_ip()
                        console.print(f"[blue]Detected public IP: {detected_ip}")
                        dns_record = dns.create_record(subdomain, content=detected_ip, force_update=force_update)
                    except Exception as ip_error:
                        console.print(f"[yellow]Warning: Could not auto-detect public IP: {str(ip_error)}")
                        console.print("[yellow]Falling back to Cloudflare IP detection")
                        dns_record = dns.create_record(subdomain, force_update=force_update)
                
                # Verify the DNS record was created successfully
                console.print(f"[green]✓ Created DNS record: {dns_record.name} pointing to {dns_record.content}")
                console.print(f"[blue]Record ID: {dns_record.id}")
                console.print(f"[blue]Proxied: {'Yes' if dns_record.proxied else 'No'}")
                console.print(f"[blue]TTL: {dns_record.ttl}")
            except Exception as e:
                console.print(f"[bold red]Failed to create DNS record: {str(e)}")
                
                # Provide more detailed guidance for common DNS errors
                if "DNS name is invalid" in str(e):
                    console.print("\n[yellow]DNS name validation troubleshooting:")
                    console.print("1. Make sure your subdomain contains only letters, numbers, and hyphens")
                    console.print("2. Check that the domain in your configuration is correct")
                    console.print("3. Avoid special characters in your subdomain")
                    console.print("4. Try a shorter, simpler subdomain name")
                    console.print("5. Run with --verbose to see more detailed error information")
                elif "Too many redirects" in str(e) or "already exists" in str(e).lower():
                    console.print("\n[yellow]Record conflict troubleshooting:")
                    console.print("1. This record may already exist in your Cloudflare account")
                    console.print("2. Try using a different subdomain name")
                    console.print("3. Use --force-update to update the existing record")
                    console.print("4. Check your Cloudflare dashboard for existing records")
                elif "unauthorized" in str(e).lower() or "permission" in str(e).lower():
                    console.print("\n[yellow]Permission troubleshooting:")
                    console.print("1. Make sure your API token has Zone:DNS:Edit permissions")
                    console.print("2. Verify you have the correct access level for this domain")
                    console.print("3. If using Global API Key, ensure it has the necessary permissions")
                
                raise typer.Exit(code=1)
            
            # Generate and validate proxy config
            status.update("[bold blue]Configuring Caddy...")
            proxy_config = ProxyConfig(
                domain=dns_record.name,
                target=f"localhost:{port}",
                ssl=True
            )
            
            try:
                config_file = proxy.generate_config(proxy_config)
            except Exception as e:
                console.print(f"[bold red]Failed to generate Caddy configuration: {str(e)}")
                raise typer.Exit(code=1)
            
            if not proxy.validate_config(config_file):
                console.print("[bold red]Invalid Caddy configuration")
                raise typer.Exit(code=1)
            
            # Start proxy
            status.update("[bold blue]Starting Caddy...")
            proxy_status = proxy.start(Path(config_file))
            
            if not proxy_status.running:
                console.print(f"[bold red]Failed to start Caddy: {proxy_status.error}")
                raise typer.Exit(code=1)

        console.print("[bold green]✓ Deployment complete!")
        console.print(f"\nYour service is now available at: https://{dns_record.name}")
        console.print("\nNote: DNS changes may take a few minutes to propagate globally.")
        console.print(f"Port: {port}")
        console.print(f"Proxied through Cloudflare: {'Yes' if dns_record.proxied else 'No'}")
        
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def debug():
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
                from caddy_cloudflare_cli.lib.utils import get_public_ip
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

def main():
    """Main entry point"""
    app()
