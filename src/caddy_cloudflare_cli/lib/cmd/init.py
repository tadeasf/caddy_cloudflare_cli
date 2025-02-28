"""
Init command implementation for Caddy Cloudflare CLI
"""
import typer
from rich.console import Console

from ..config import Config

console = Console()

def init_command():
    """Initialize Caddy Cloudflare CLI configuration"""
    try:
        config = Config.initialize_interactive()
        console.print("[bold green]✓ Configuration initialized successfully!")
        console.print(f"\nYou can now use other commands like 'install' and 'deploy' with domain {config.domain}.")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1) 