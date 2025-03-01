"""
Proxy command implementations for Caddy Cloudflare CLI
"""

import typer
from rich.console import Console

from ..config import Config, ConfigError
from ..proxy.caddy import CaddyProxy

console = Console()

def start_command(config_file=None):
    """Start the Caddy proxy server"""
    import subprocess
    from pathlib import Path
    
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        # Convert config_file to Path if it's a string
        if isinstance(config_file, str):
            config_file = Path(config_file)
        
        # Check if port 443 is in use by another program
        if proxy._is_port_in_use(443):
            # Check if it's the systemd Caddy service
            try:
                systemctl_result = subprocess.run(
                    ["systemctl", "is-active", "caddy"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if systemctl_result.stdout.strip() == "active":
                    console.print("[bold red]! Caddy is already running as a systemd service")
                    console.print("To use this tool for Caddy management, stop the systemd service first:")
                    console.print("  sudo systemctl stop caddy")
                    console.print("  sudo systemctl disable caddy")
                    raise typer.Exit(code=1)
            except Exception:
                # Ignore errors if systemctl is not available
                pass
                
            # Otherwise, just report port conflict
            console.print("[bold red]! Port 443 is already in use by another program")
            
            # Try to show what's using the port
            try:
                proc = subprocess.run(
                    ["lsof", "-i", ":443", "-P", "-n"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if proc.stdout:
                    console.print("The following process is using port 443:")
                    console.print(proc.stdout)
            except Exception:
                pass
                
            console.print("Please stop the other program first, then try again.")
            raise typer.Exit(code=1)
        
        # Check if Caddy is running first
        is_running = proxy.status()
        
        if is_running:
            console.print("[bold yellow]! Caddy is already running")
            return
        
        # Generate configuration if needed
        if not config_file:
            console.print("Generating Caddy configuration...")
            try:
                config_file = proxy.generate_config()
                console.print(f"Generated configuration at {config_file}")
            except Exception as e:
                console.print(f"[bold red]Error generating configuration: {e}")
                raise typer.Exit(code=1)
        
        # Start Caddy with the specified config file
        console.print(f"Starting Caddy with configuration at {config_file}...")
        
        result = proxy.start(config_file)
        
        if result:
            pid = proxy._get_pid()
            console.print("[bold green]✓ Caddy is running")
            console.print(f"PID: {pid}")
            console.print(f"Config: {proxy.caddyfile_path}")
            
            # Verify binding to port 443
            if proxy._verify_process_binding(pid, 443):
                console.print("[bold green]✓ Successfully bound to port 443")
            else:
                console.print("[bold yellow]! Warning: Caddy is running but may not be properly bound to port 443")
                console.print("  This could indicate permission issues or a port conflict")
        else:
            console.print("[bold red]! Failed to start Caddy")
            console.print("\nTroubleshooting tips:")
            console.print("1. Check if another process is using port 443")
            console.print("   lsof -i :443 -P -n")
            console.print("2. Verify your configuration is valid")
            console.print("   caddy validate --config your_caddyfile")
            console.print("3. Check system logs for more details")
            console.print("   journalctl -e | grep caddy")
            raise typer.Exit(code=1)
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error while starting Caddy: {str(e)}")
        raise typer.Exit(code=1)

def stop_command():
    """Stop the Caddy proxy server"""
    
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        # Check if Caddy is running first
        is_running = proxy.status()
        
        if not is_running:
            console.print("[bold yellow]! Caddy is not running")
            return
        
        # Get PID before stopping for informational purposes
        pid = proxy._get_pid()
        
        console.print("Stopping Caddy...")
        
        # Try to stop Caddy process
        result = proxy.stop()
        
        if result:
            if pid:
                console.print(f"[bold green]✓ Caddy process with PID {pid} stopped successfully")
            else:
                console.print("[bold green]✓ Caddy stopped successfully")
            return
        else:
            console.print("[bold red]! Failed to stop Caddy")
            
            # Offer manual kill guidance
            console.print("\n[yellow]Try these commands to manually kill Caddy:")
            console.print("  pgrep -f caddy")
            console.print("  kill -9 <PID>")
            raise typer.Exit(code=1)
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error while stopping Caddy: {str(e)}")
        raise typer.Exit(code=1)

def status_command():
    """Show the Caddy proxy server status"""
    import subprocess
    
    try:
        config = Config.load()
        proxy = CaddyProxy(config)
        
        # First check if the systemd Caddy service is running
        try:
            systemctl_result = subprocess.run(
                ["systemctl", "is-active", "caddy"],
                capture_output=True,
                text=True,
                check=False
            )
            if systemctl_result.stdout.strip() == "active":
                console.print("[bold yellow]! Caddy is running as a systemd service")
                console.print("Note: This may conflict with the CLI tool's Caddy management")
        except Exception:
            # Ignore errors if systemctl is not available
            pass
        
        # Check our Caddy status 
        is_running = proxy.status()
        
        if is_running:
            pid = proxy._get_pid()
            console.print("[bold green]✓ Caddy is running")
            console.print(f"PID: {pid}")
            console.print(f"Config: {proxy.caddyfile_path}")
            
            # Get actual process info to ensure we're showing the right information
            try:
                cmd_result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "pid,cmd", "--no-headers"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if cmd_result.returncode == 0:
                    process_info = cmd_result.stdout.strip()
                    console.print(f"Process: {process_info}")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not get process info: {e}")
                
            # Check if there are other Caddy processes running
            try:
                caddy_pids = proxy._find_caddy_processes()
                if len(caddy_pids) > 1:
                    other_pids = [p for p in caddy_pids if p != pid]
                    if other_pids:
                        console.print(f"[bold yellow]! Found {len(other_pids)} other Caddy processes: {', '.join(map(str, other_pids))}")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not check for other Caddy processes: {e}")
                
            # Always use lsof to check port binding to be more reliable
            port_in_use = False
            our_process_binding = False
            
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-i", ":443", "-P", "-n"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if lsof_result.returncode == 0 and lsof_result.stdout:
                    port_in_use = True
                    # Check if it's our process
                    if str(pid) in lsof_result.stdout and "LISTEN" in lsof_result.stdout:
                        our_process_binding = True
                        console.print("[bold green]✓ Successfully bound to port 443")
                        # Show more details about the port binding
                        for line in lsof_result.stdout.strip().split('\n'):
                            if str(pid) in line and "LISTEN" in line:
                                console.print(f"Port binding: {line}")
                    else:
                        # Check if any of our Caddy processes are binding to port 443
                        for p in caddy_pids:
                            if str(p) in lsof_result.stdout and "LISTEN" in lsof_result.stdout:
                                our_process_binding = True
                                console.print(f"[bold green]✓ Caddy process with PID {p} is bound to port 443")
                                # Show more details about the port binding
                                for line in lsof_result.stdout.strip().split('\n'):
                                    if str(p) in line and "LISTEN" in line:
                                        console.print(f"Port binding: {line}")
                                # Update our PID file to reflect the correct process
                                proxy._save_pid(p)
                                break
            except Exception as e:
                console.print(f"[yellow]Warning: Could not check port binding: {e}")
            
            if port_in_use and not our_process_binding:
                console.print("[bold yellow]! Warning: Port 443 is in use by another process")
                try:
                    console.print("Port 443 is in use by:")
                    console.print(lsof_result.stdout)
                except Exception:
                    pass
                    
            elif not port_in_use:
                console.print("[bold red]! Error: Port 443 is not in use by any process")
                console.print("Caddy is running but not binding to port 443")
                
                # Try to check what ports our Caddy is using
                try:
                    for p in caddy_pids:
                        lsof_pid_result = subprocess.run(
                            ["lsof", "-i", "-P", "-n", "-p", str(p)],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if lsof_pid_result.returncode == 0 and lsof_pid_result.stdout:
                            console.print(f"Caddy process {p} is using these network connections:")
                            console.print(lsof_pid_result.stdout)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not check Caddy network connections: {e}")
            
            # Show more process details using ps
            try:
                proc = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,command"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if proc.stdout:
                    console.print("\nProcess details:")
                    console.print(proc.stdout)
            except Exception:
                pass
                
            # Show the log file if it exists
            log_file = proxy.dirs['data'] / 'logs' / 'caddy.log'
            if log_file.exists():
                try:
                    # Show the last 10 lines of the log file
                    tail_cmd = ["tail", "-n", "10", str(log_file)]
                    tail_result = subprocess.run(tail_cmd, capture_output=True, text=True, check=False)
                    if tail_result.stdout:
                        console.print("\nLast 10 lines of log file:")
                        console.print(tail_result.stdout)
                except Exception:
                    pass
            else:
                console.print(f"\n[yellow]Warning: Log file not found at {log_file}")
                # Try to check if there's any log file in the data directory
                try:
                    log_dir = proxy.dirs['data'] / 'logs'
                    if log_dir.exists():
                        log_files = list(log_dir.glob('*.log'))
                        if log_files:
                            console.print(f"Found these log files: {', '.join(str(f) for f in log_files)}")
                    else:
                        console.print(f"Log directory {log_dir} does not exist.")
                        # Create it
                        log_dir.mkdir(parents=True, exist_ok=True)
                        console.print(f"Created log directory at {log_dir}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Error checking for log files: {e}")
        else:
            console.print("[bold red]! Caddy is not running")
            
            # Check if port 443 is in use by another program
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-i", ":443", "-P", "-n"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if lsof_result.returncode == 0 and lsof_result.stdout:
                    console.print("[bold yellow]! Port 443 is in use by another program")
                    console.print("This may prevent Caddy from starting properly.")
                    console.print("Port 443 is in use by:")
                    console.print(lsof_result.stdout)
            except Exception:
                pass
            
            console.print("\nTo start Caddy, run:")
            console.print("  caddy-cloudflare proxy start")
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
        
        console.print("Reloading Caddy configuration...")
        if proxy.reload():
            console.print("[bold green]✓ Configuration reloaded successfully")
        else:
            console.print("[bold red]Failed to reload configuration")
            raise typer.Exit(code=1)
            
    except ConfigError as e:
        console.print(f"[bold red]Configuration error: {str(e)}")
        console.print("Please run 'caddy-cloudflare init' to initialize the configuration.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise typer.Exit(code=1) 