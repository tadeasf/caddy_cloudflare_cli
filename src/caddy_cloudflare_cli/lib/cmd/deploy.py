"""
Deploy command implementation for Caddy Cloudflare CLI
"""
import logging
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt

from ..config import Config, ConfigError
# Import utils directly as a module, not just the function
import caddy_cloudflare_cli.lib.utils as utils
from ..dns.cloudflare_api_handler import CloudflareDNS
from ..proxy.caddy import CaddyProxy
from ..proxy.base import ProxyConfig
from .port import validate_port, is_port_in_use, suggest_available_port, DEFAULT_PORTS
from .domain import generate_random_subdomain, validate_subdomain

console = Console()

def deploy_command(
    subdomain: Optional[str] = None,
    port: Optional[int] = None,
    interactive: bool = False,
    config: Optional[Path] = None,
    verify_credentials: bool = False,
    verbose: bool = False,
    log_level: str = "INFO",
    public_ip: Optional[str] = None,
    force_update: bool = False,
    force_port: bool = False,
    debug: bool = False,
) -> None:
    """
    Deploy with Cloudflare DNS tunnel.
    
    Sets up a Cloudflare DNS record for a subdomain and configures Caddy as a reverse proxy.
    The subdomain will be generated randomly if not provided.
    
    This tool is designed for rapidly deploying subdomains for internal tooling and home labs.
    """
    import traceback
    
    try:
        # Configure logging based on options
        if debug:
            verbose = True
            log_level = "DEBUG"
        elif verbose:
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
        
        # Load configuration
        config_obj = Config.load()
        
        # Verify credentials if requested
        if verify_credentials:
            console.print("[bold blue]Verifying Cloudflare credentials...")
            
            # Show which auth method is configured
            has_valid_token = bool(config_obj.cloudflare_token and config_obj.cloudflare_token.strip())
            has_valid_api_key = bool(config_obj.cloudflare_api_key and config_obj.cloudflare_api_email and 
                                     config_obj.cloudflare_api_key.strip() and config_obj.cloudflare_api_email.strip())
            has_valid_dual_tokens = bool(config_obj.cloudflare_zone_token and config_obj.cloudflare_dns_token and
                                     config_obj.cloudflare_zone_token.strip() and config_obj.cloudflare_dns_token.strip())
            
            if has_valid_dual_tokens:
                console.print("[blue]Using Zone and DNS Token authentication (least privilege)")
                console.print(f"Zone Token (masked): {config_obj.cloudflare_zone_token[:4]}...{config_obj.cloudflare_zone_token[-4:] if len(config_obj.cloudflare_zone_token) > 8 else '****'}")
                console.print(f"DNS Token (masked): {config_obj.cloudflare_dns_token[:4]}...{config_obj.cloudflare_dns_token[-4:] if len(config_obj.cloudflare_dns_token) > 8 else '****'}")
            elif has_valid_token:
                console.print("[blue]Using API Token authentication")
                console.print(f"Token (masked): {config_obj.cloudflare_token[:4]}...{config_obj.cloudflare_token[-4:] if len(config_obj.cloudflare_token) > 8 else '****'}")
            elif has_valid_api_key:
                console.print("[blue]Using Global API Key authentication")
                console.print(f"Email: {config_obj.cloudflare_api_email}")
                console.print(f"API Key (masked): {config_obj.cloudflare_api_key[:4]}...{config_obj.cloudflare_api_key[-4:] if len(config_obj.cloudflare_api_key) > 8 else '****'}")
            else:
                console.print("[bold red]No valid Cloudflare credentials configured")
                console.print("Please run 'caddy-cloudflare init' to set up credentials")
                return
                
            try:
                # Initialize CloudflareDNS instance
                dns = CloudflareDNS(config_obj)
                
                # Test API access by listing zones
                zone_id = dns.zone_id  # This will test API access and domain lookup
                console.print("[bold green]✓ Successfully authenticated with Cloudflare")
                console.print(f"[bold green]✓ Found zone ID for domain {config_obj.domain}: {zone_id}")
                return
            except Exception as e:
                console.print(f"[bold red]Error: {str(e)}")
                return
                
        # Interactive mode if parameters not provided
        if subdomain is None:
            if interactive:
                # In interactive mode, ask for subdomain or generate one
                use_random = Confirm.ask(
                    "Generate a random subdomain?",
                    default=True
                )
                
                if use_random:
                    subdomain = generate_random_subdomain()
                    console.print(f"[bold blue]Generated random subdomain: {subdomain}")
                    
                    # Confirm if they want to use this subdomain
                    use_this = Confirm.ask(
                        "Use this subdomain?",
                        default=True
                    )
                    
                    if not use_this:
                        # If they don't want the random one, prompt for custom
                        subdomain = Prompt.ask(
                            "Enter custom subdomain",
                            default=""
                        )
                else:
                    # If they don't want random, prompt for custom
                    subdomain = Prompt.ask(
                        "Enter custom subdomain",
                        default=""
                    )
            else:
                # In non-interactive mode, just generate a random subdomain
                subdomain = generate_random_subdomain()
                console.print(f"Generated random subdomain: {subdomain}")
        
        # Handle empty subdomain (generate random one)
        if subdomain == "":
            subdomain = generate_random_subdomain()
            console.print(f"Generated random subdomain: {subdomain}")
        
        # Validate subdomain if provided
        if not validate_subdomain(subdomain):
            console.print("[bold red]Invalid subdomain format")
            console.print("Subdomains should contain only letters, numbers, and hyphens, and not start or end with a hyphen.")
            raise typer.Exit(code=1)
            
        # Handle port selection
        if port is None:
            # Find an available port to suggest
            available_port = suggest_available_port(8080)
            
            if interactive:
                # Show a list of common ports with their status
                console.print("[bold]Select a port for your local service:[/bold]")
                for i, default_port in enumerate(DEFAULT_PORTS, 1):
                    status = "[green]available" if not is_port_in_use(default_port) else "[red]in use"
                    console.print(f"  {i}. {default_port} - {status}")
                
                console.print(f"  {len(DEFAULT_PORTS) + 1}. {available_port} - [green]available (auto-detected)")
                console.print(f"  {len(DEFAULT_PORTS) + 2}. Custom port")
                
                # Ask user to choose
                choice = IntPrompt.ask(
                    "Select a port option",
                    default=len(DEFAULT_PORTS) + 1,  # Default to the suggested available port
                    choices=[str(i) for i in range(1, len(DEFAULT_PORTS) + 3)]
                )
                
                if choice <= len(DEFAULT_PORTS):
                    selected_port = DEFAULT_PORTS[choice - 1]
                    if is_port_in_use(selected_port) and not force_port:
                        console.print(f"[yellow]Warning: Port {selected_port} is already in use")
                        if Confirm.ask("Do you still want to use this port?", default=False):
                            port = selected_port
                        else:
                            port = available_port
                    else:
                        port = selected_port
                elif choice == len(DEFAULT_PORTS) + 1:
                    port = available_port
                else:
                    custom_port = IntPrompt.ask(
                        "Enter a custom port (1-65535)", 
                        default=available_port
                    )
                    
                    if not validate_port(custom_port):
                        console.print("[yellow]Invalid port number, using suggested available port")
                        port = available_port
                    elif is_port_in_use(custom_port) and not force_port:
                        console.print(f"[yellow]Warning: Port {custom_port} is already in use")
                        if Confirm.ask("Do you still want to use this port?", default=False):
                            port = custom_port
                        else:
                            port = available_port
                    else:
                        port = custom_port
            else:
                # Non-interactive mode, just use the suggested port
                port = available_port
                console.print(f"Using port {port} (automatically selected)")
        elif interactive:
            # If port is provided but interactive mode is on, confirm the port choice
            if is_port_in_use(port) and not force_port:
                console.print(f"[yellow]Warning: The specified port {port} is already in use")
                if not Confirm.ask("Do you still want to use this port?", default=False):
                    available_port = suggest_available_port(8080)
                    console.print(f"Using suggested available port {available_port} instead")
                    port = available_port
            else:
                console.print(f"Using specified port: {port}")
        
        # Validate the port
        if not validate_port(port):
            console.print(f"[bold red]Invalid port: {port}")
            console.print("Port must be between 1 and 65535")
            raise typer.Exit(code=1)
            
        if is_port_in_use(port) and not interactive and not force_port:
            console.print(f"[yellow]Warning: Port {port} is already in use")
            console.print("Use --force-port to force using this port anyway")
            console.print("[yellow]Continuing with deployment, but your service might not work properly")

        # Initialize providers
        try:
            # Show authentication method being used
            if config_obj.cloudflare_zone_token and config_obj.cloudflare_dns_token:
                console.print("[blue]Using Cloudflare Zone and DNS Tokens for authentication (least privilege)")
            elif config_obj.cloudflare_token:
                console.print("[blue]Using Cloudflare API Token for authentication")
            elif config_obj.cloudflare_api_key and config_obj.cloudflare_api_email:
                console.print("[blue]Using Cloudflare Global API Key for authentication")
            else:
                console.print("[bold red]No valid Cloudflare credentials found")
                console.print("Please run 'caddy-cloudflare init' to set up your credentials")
                raise typer.Exit(code=1)
                
            dns = CloudflareDNS(config_obj)
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

        proxy = CaddyProxy(config_obj)

        with console.status("[bold green]Deploying service...") as status:
            # Create DNS record
            status.update("[bold blue]Creating DNS record...")
            try:
                # If public_ip was specified in the command, use it
                content = public_ip
                
                if content:
                    console.print(f"[blue]Using provided public IP: {content}")
                    dns_record = dns.create_record(subdomain, content=content, force_update=force_update)
                elif config_obj.public_ip:
                    console.print(f"[blue]Using configured public IP: {config_obj.public_ip}")
                    dns_record = dns.create_record(subdomain, force_update=force_update)
                else:
                    console.print("[blue]Auto-detecting public IP address...")
                    try:
                        detected_ip = utils.get_public_ip()
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
            proxy_started = proxy.start(config_file)
            
            if not proxy_started:
                console.print("[bold red]Failed to start Caddy")
                raise typer.Exit(code=1)

        console.print("\n[bold green]✓ Deployment complete!")
        console.print(f"\n[bold]Your service is now available at: [link=https://{dns_record.name}]https://{dns_record.name}[/link]")
        console.print("\n[bold]Configuration Details:[/bold]")
        console.print(f"  - [blue]Domain: [white]{dns_record.name}")
        console.print(f"  - [blue]Target: [white]localhost:{port}")
        console.print(f"  - [blue]Public IP: [white]{dns_record.content}")
        console.print(f"  - [blue]Proxied through Cloudflare: [white]{'Yes' if dns_record.proxied else 'No'}")
        console.print(f"  - [blue]DNS Record ID: [white]{dns_record.id}")
        console.print(f"  - [blue]TTL: [white]{dns_record.ttl}")
        
        console.print("\n[yellow]Note: DNS changes may take a few minutes to propagate globally.")
        
        if interactive:
            console.print("\n[blue]Commands to manage this deployment:[/blue]")
            console.print("  - [white]caddy-cloudflare list[/white] - View all deployments")
            console.print(f"  - [white]caddy-cloudflare delete {subdomain}[/white] - Remove this deployment")
        
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        if debug:
            console.print("\nFull traceback:")
            console.print(traceback.format_exc())
        raise typer.Exit(code=1) 