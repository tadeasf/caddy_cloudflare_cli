"""
Command-line interface for Caddy Cloudflare CLI
"""
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console

from .lib.cmd import (
    # Command implementations
    deploy_command,
    init_command,
    install_command, 
    uninstall_command,
    start_command, 
    stop_command, 
    status_command, 
    reload_command,
    debug_command
)

console = Console()
app = typer.Typer(help="Caddy Cloudflare CLI - Easy DNS and reverse proxy setup")
proxy_app = typer.Typer(help="Manage the Caddy proxy server")
app.add_typer(proxy_app, name="proxy")

# Constants
DEFAULT_CONFIG_FILE = "~/.caddy-cloudflare/config.json"

@app.command()
def init():
    """Initialize Caddy Cloudflare CLI configuration"""
    return init_command()

@proxy_app.command()
def start(config: Optional[Path] = typer.Option(None, '--config', '-c', help='Path to Caddyfile')):
    """Start the Caddy proxy server"""
    return start_command(config)

@proxy_app.command()
def stop():
    """Stop the Caddy proxy server"""
    return stop_command()

@proxy_app.command()
def status():
    """Show the Caddy proxy server status"""
    return status_command()

@proxy_app.command()
def reload():
    """Reload the Caddy proxy configuration"""
    return reload_command()

@app.command()
def install():
    """Install the Caddy binary"""
    return install_command()

@app.command()
def uninstall():
    """Uninstall the Caddy binary"""
    return uninstall_command()

@app.command()
def deploy(
    subdomain: Optional[str] = typer.Option(None, '--subdomain', '-s', help='Custom subdomain (random if not provided)'),
    port: Optional[int] = typer.Option(None, '--port', '-p', help='Port to forward (interactive if not provided)'),
    force_port: bool = typer.Option(False, '--force-port', '-fp', help='Force using the specified port even if in use'),
    force_root: bool = typer.Option(False, '--force-root', '-fr', help='Use root domain instead of subdomain'),
    use_ip: Optional[str] = typer.Option(None, '--ip', '-i', help='Public IP to use (auto-detect if not provided)'),
    show_token: bool = typer.Option(False, '--show-token', help='Show API tokens in output (security risk)'),
    debug: bool = typer.Option(False, '--debug', '-d', help='Enable debug logging')
):
    """
    Deploy a local service with Cloudflare DNS and Caddy
    
    This command:
    1. Creates a DNS record for your subdomain pointing to your public IP
    2. Starts Caddy as a reverse proxy to your local service
    """
    return deploy_command(subdomain, port, force_port, force_root, use_ip, show_token, debug=debug)

@app.command()
def debug():
    """Debug authentication and connection issues"""
    return debug_command()

def main():
    """Main entry point"""
    app()

if __name__ == "__main__":
    main()
