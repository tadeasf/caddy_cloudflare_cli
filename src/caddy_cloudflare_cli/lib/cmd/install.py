"""
Install and uninstall command implementations for Caddy Cloudflare CLI
"""
import typer
from rich.console import Console
from rich.prompt import Confirm

from ..config import Config, ConfigError
from ..proxy.caddy import CaddyProxy

console = Console()

def install_command(system: bool = False):
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

def uninstall_command():
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