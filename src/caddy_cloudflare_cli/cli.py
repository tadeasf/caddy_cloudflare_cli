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
    debug_command,
    list_command,
    delete_command
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
    return start_command(config_file=config)

@proxy_app.command()
def stop():
    """Stop the Caddy proxy server"""
    # No need to set up signal handlers
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
def list(
    show_all: bool = typer.Option(False, '--all', '-a', help='Show all DNS records, not just deployed ones'),
    debug: bool = typer.Option(False, '--debug', '-d', help='Enable debug logging')
):
    """List all deployed subdomains"""
    return list_command(show_all=show_all, debug=debug)

@app.command()
def delete(
    subdomain: str = typer.Argument(..., help='Subdomain to delete, without the domain part (e.g. "test" for test.example.com)'),
    force: bool = typer.Option(False, '--force', '-f', help='Delete without confirmation'),
    debug: bool = typer.Option(False, '--debug', '-d', help='Enable debug logging')
):
    """Delete a deployed subdomain"""
    return delete_command(subdomain=subdomain, force=force, debug=debug)

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
    return deploy_command(
        subdomain=subdomain, 
        port=port, 
        interactive=True,
        public_ip=use_ip,
        debug=debug,
        verify_credentials=show_token,
        force_update=force_root,
        force_port=force_port
    )

@app.command()
def debug():
    """Debug authentication and connection issues"""
    return debug_command()

def main():
    """Main entry point"""
    import os
    import sys
    import logging
    
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Make sure we're using the correct Python executable
    python_executable = sys.executable
    logging.debug(f"Python executable: {python_executable}")
    
    # Print helpful debugging info
    logging.debug(f"Python path: {sys.path}")
    logging.debug(f"Current directory: {os.getcwd()}")
    
    # Set locale to avoid warnings
    try:
        import locale
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except Exception:
        pass  # Ignore if this fails
        
    # Run the app
    app()

if __name__ == "__main__":
    main()
