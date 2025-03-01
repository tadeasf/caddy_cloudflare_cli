"""
Management commands implementation for Caddy Cloudflare CLI (list and delete)
"""
import logging

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from ..config import Config, ConfigError
from ..dns.cloudflare_api_handler import CloudflareDNS
from ..proxy.caddy import CaddyProxy

console = Console()
logger = logging.getLogger("caddy_cloudflare_cli.lib.cmd.manage")

def list_command(
    show_all: bool = False,
    debug: bool = False
) -> None:
    """
    List all deployed subdomains
    
    Lists all DNS records for the configured domain that were deployed using the CLI.
    """
    try:
        # Set up logging for debugging
        if debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        
        # Load configuration
        config = Config.load()
        
        # Create Cloudflare DNS handler
        dns_handler = CloudflareDNS(config)
        
        # Show status message
        console.print("[bold blue]Fetching DNS records from Cloudflare...")
        
        # Get all DNS records for the domain (filtering will happen in display logic)
        try:
            all_records = dns_handler.list_records()
            logger.info(f"Found {len(all_records)} total DNS records for {config.domain}")
        except Exception as e:
            console.print(f"[bold red]Failed to fetch DNS records: {e}")
            raise typer.Exit(code=1)
        
        # Create a table to display the records
        table = Table(title=f"DNS Records for {config.domain}")
        table.add_column("Subdomain", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Content", style="green")
        table.add_column("Proxied", style="yellow")
        table.add_column("TTL", style="blue")
        table.add_column("ID", style="dim")
        
        # No records found
        if not all_records:
            console.print("[yellow]No DNS records found for this domain")
            raise typer.Exit(code=0)
        
        # Process and display records
        processed_records = []
        base_domain = config.domain.lower()
        
        # Filter and process records
        for record in all_records:            
            # Skip root domain records unless show_all is True
            if record.name.lower() == base_domain and not show_all:
                continue
                
            # Skip non-A and non-CNAME records unless show_all is True
            if record.type not in ['A', 'CNAME'] and not show_all:
                continue
            
            # Format domain name to show just the subdomain part
            if record.name.lower().endswith(f".{base_domain}"):
                display_name = record.name.lower().removesuffix(f".{base_domain}")
                # If empty, it's the root domain
                if not display_name:
                    display_name = "@"
            else:
                display_name = record.name
            
            table.add_row(
                display_name,
                record.type,
                record.content,
                "Yes" if record.proxied else "No",
                str(record.ttl) if record.ttl != 1 else "Auto",
                record.id
            )
            processed_records.append(record)
        
        # No records found after filtering
        if not processed_records:
            console.print("[yellow]No matching DNS records found. Use --show-all to see all records.")
            raise typer.Exit(code=0)
        
        # Display the table
        console.print(table)
        
        # Show help text for managing records
        console.print("\n[bold blue]Management commands:[/bold blue]")
        console.print("  [white]caddy-cloudflare delete <subdomain>[/white] - Delete a specific deployment")
        
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        if debug:
            console.print("\nFull traceback:")
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)

def delete_command(
    subdomain: str,
    force: bool = False,
    debug: bool = False
) -> None:
    """
    Delete a deployed subdomain
    
    Removes the DNS record for the specified subdomain and stops the Caddy proxy if it's running.
    """
    try:
        # Set up logging for debugging
        if debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        
        # Load configuration
        config = Config.load()
        
        # Create Cloudflare DNS handler
        dns_handler = CloudflareDNS(config)
        
        # Create Caddy proxy handler
        proxy = CaddyProxy(config)
        
        # Format subdomain for lookup
        if subdomain == "@":
            # Root domain
            full_domain = config.domain
            display_name = f"root domain ({config.domain})"
        elif "." in subdomain and subdomain.endswith(config.domain):
            # Full domain provided
            full_domain = subdomain
            subdomain_part = subdomain.removesuffix(f".{config.domain}")
            display_name = f"{subdomain_part}.{config.domain}"
        else:
            # Subdomain only provided
            full_domain = f"{subdomain}.{config.domain}"
            display_name = full_domain
        
        # Find the DNS record
        console.print(f"[bold blue]Looking up DNS record for {display_name}...")
        
        matching_records = dns_handler.list_dns_records(name=full_domain)
        
        if not matching_records:
            console.print(f"[bold yellow]No DNS record found for {display_name}")
            raise typer.Exit(code=1)
        
        # Found matching record(s)
        dns_record = matching_records[0]
        
        # Display record details
        console.print(f"[green]Found DNS record:[/green] {dns_record.name} ({dns_record.type}) -> {dns_record.content}")
        
        # Confirm deletion unless force is specified
        if not force and not Confirm.ask("[yellow]Are you sure you want to delete this record?"):
            console.print("[yellow]Operation cancelled")
            raise typer.Exit(code=0)
        
        # Delete the DNS record
        console.print("[bold blue]Deleting DNS record...")
        try:
            dns_handler.delete_record(dns_record.id)
            console.print(f"[bold green]✓ DNS record deleted for {display_name}")
        except Exception as e:
            console.print(f"[bold red]Failed to delete DNS record: {e}")
            raise typer.Exit(code=1)
        
        # Stop Caddy server if it's running
        console.print("[bold blue]Checking if Caddy proxy needs to be stopped...")
        if proxy.status():
            console.print("[bold blue]Stopping Caddy proxy...")
            try:
                proxy.stop()
                console.print("[bold green]✓ Caddy proxy stopped")
            except Exception as e:
                console.print(f"[bold yellow]Warning: Could not stop Caddy proxy: {e}")
                console.print("You may need to manually stop it with 'caddy-cloudflare proxy stop'")
        else:
            console.print("[green]No running Caddy proxy found for this deployment")
        
        console.print("\n[bold green]✓ Deployment deleted successfully")
        
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        if debug:
            console.print("\nFull traceback:")
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1) 