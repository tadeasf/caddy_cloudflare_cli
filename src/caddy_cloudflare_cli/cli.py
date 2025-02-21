"""
Command-line interface for Caddy Cloudflare CLI
"""
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .lib.dns.cloudflare import CloudflareDNS
from .lib.proxy.caddy import CaddyProxy
from .lib.proxy.base import ProxyConfig
from .lib.config import Config
from .lib.utils import validate_subdomain, validate_port

console = Console()

@click.group()
@click.version_option()
def cli():
    """Caddy Cloudflare CLI - Easy DNS and reverse proxy setup"""
    pass

@cli.command()
@click.option('--subdomain', '-s', help='Subdomain to use (auto-generated if not provided)')
@click.option('--port', '-p', type=int, help='Target service port')
def deploy(subdomain: Optional[str], port: Optional[int]):
    """Deploy a new service with DNS and reverse proxy"""
    try:
        # Load configuration
        config = Config.load()
        
        # Interactive mode if parameters not provided
        if not subdomain:
            subdomain = Prompt.ask("Enter subdomain (leave empty for auto-generation)")
            if subdomain and not validate_subdomain(subdomain):
                raise click.BadParameter("Invalid subdomain format")
        
        if not port:
            port = Prompt.ask("Enter target service port", type=int)
            if not validate_port(port):
                raise click.BadParameter("Invalid port number")

        # Initialize providers
        dns = CloudflareDNS(config)
        proxy = CaddyProxy(config)

        with console.status("[bold green]Deploying service...") as status:
            # Create DNS record
            status.update("[bold blue]Creating DNS record...")
            dns_record = dns.create_record(subdomain)
            
            # Generate and validate proxy config
            status.update("[bold blue]Configuring Caddy...")
            proxy_config = ProxyConfig(
                domain=dns_record.name,
                target=f"localhost:{port}",
                ssl=True
            )
            config_file = proxy.generate_config(proxy_config)
            
            if not proxy.validate_config(config_file):
                raise click.BadParameter("Invalid Caddy configuration")
            
            # Start proxy
            status.update("[bold blue]Starting Caddy...")
            proxy_status = proxy.start(Path(config_file))
            
            if not proxy_status.running:
                raise click.BadParameter(f"Failed to start Caddy: {proxy_status.error}")

        console.print("[bold green]✓ Deployment complete!")
        console.print(f"\nYour service is now available at: https://{dns_record.name}")
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

@cli.command()
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
                
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

@cli.command()
def stop():
    """Stop proxy server"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.stop():
            console.print("[bold green]✓ Caddy stopped successfully")
        else:
            console.print("[bold yellow]! Caddy was not running")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

@cli.command()
def reload():
    """Reload proxy configuration"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.reload():
            console.print("[bold green]✓ Configuration reloaded successfully")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

@cli.command()
@click.option('--system', is_flag=True, help='Install system-wide')
def install(system: bool):
    """Install Caddy binary"""
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.install(system_wide=system):
            console.print("[bold green]✓ Caddy installed successfully")
            if system:
                console.print("Caddy is now available system-wide at: /usr/local/bin/caddy")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

@cli.command()
def uninstall():
    """Uninstall Caddy"""
    try:
        if not Confirm.ask("Are you sure you want to uninstall Caddy?"):
            return
            
        config = Config.load()
        proxy = CaddyProxy(config)
        
        if proxy.uninstall():
            console.print("[bold green]✓ Caddy uninstalled successfully")
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()

def main():
    """Main entry point"""
    cli()
