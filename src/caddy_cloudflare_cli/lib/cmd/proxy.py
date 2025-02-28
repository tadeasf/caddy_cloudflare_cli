"""
Proxy command implementations for Caddy Cloudflare CLI
"""
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console

from ..config import Config, ConfigError
from ..proxy.caddy import CaddyProxy

console = Console()

def start_command(config: Optional[Path] = None):
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

def stop_command():
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

def status_command():
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

def reload_command():
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