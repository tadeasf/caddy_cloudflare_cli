"""
Caddy proxy manager for Caddy Cloudflare CLI
"""
import logging
import os
import signal
import subprocess
import time
import socket
from pathlib import Path
from typing import Dict, Optional, Union, List

from ...config import Config
from .caddyfile import CaddyfileParser
from ..base import ProxyConfig, ProxyStatus, ReverseProxy, ProxyError

logger = logging.getLogger(__name__)

class CaddyProxy(ReverseProxy):
    """Manages Caddy proxy server"""
    
    def __init__(self, config: Config):
        """
        Initialize Caddy proxy manager
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Set up directories
        proxy_dirs = config.get_proxy_dirs()
        self.dirs = {
            'config': proxy_dirs['config'],
            'data': proxy_dirs['data'],
            'cache': proxy_dirs['cache'],
            'bin': config.data_dir / 'bin'
        }
        
        # Create directories if they don't exist
        for path in self.dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        
        # Set paths
        self.caddy_path = config.get_binary_path()
        self.caddyfile_path = self.dirs['config'] / 'Caddyfile'
        self.pid_file = self.dirs['data'] / 'caddy.pid'
        
        # Create Caddyfile parser
        self.parser = CaddyfileParser(self.caddyfile_path)
    
    def _save_pid(self, pid: int) -> None:
        """Save PID to file"""
        try:
            self.pid_file.write_text(str(pid))
            logger.info(f"Saved PID {pid} to {self.pid_file}")
        except Exception as e:
            logger.error(f"Failed to save PID file: {e}")
    
    def _get_pid(self) -> Optional[int]:
        """Get PID from file"""
        try:
            if self.pid_file.exists():
                pid = int(self.pid_file.read_text().strip())
                return pid
            return None
        except Exception as e:
            logger.error(f"Failed to read PID file: {e}")
            return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running by PID and if it's a Caddy process"""
        if pid is None:
            return False
            
        try:
            # Sending signal 0 to a process checks if it exists without affecting it
            os.kill(pid, 0)
            
            # Additional check: verify it's actually a Caddy process by checking the command line
            binary_path = str(self.caddy_path)
            try:
                # Read the process command line
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode('utf-8', errors='replace').replace('\0', ' ')
                
                # Check if it's our caddy binary (binary path match and 'run' command)
                if binary_path in cmdline and "run" in cmdline:
                    logger.debug(f"Confirmed process {pid} is a Caddy process")
                    return True
                    
                logger.warning(f"Process {pid} exists but does not appear to be a Caddy process.")
                logger.warning(f"Command line: {cmdline}")
                return False
            except (IOError, OSError):
                # Fall back to simpler check if /proc not available or other error
                logger.debug(f"Could not read /proc/{pid}/cmdline, using simplified check")
                # Use ps command to check the process command
                try:
                    cmd_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "cmd", "--no-headers"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if cmd_result.returncode == 0:
                        process_cmd = cmd_result.stdout.strip()
                        if binary_path in process_cmd and "run" in process_cmd:
                            logger.debug(f"Process {pid} is a Caddy process: {process_cmd}")
                            return True
                        else:
                            logger.warning(f"PID {pid} exists but is not a Caddy process: {process_cmd}")
                            return False
                except Exception as e:
                    logger.error(f"Error checking process command: {e}")
                return True
                
        except OSError:
            return False
    
    def _find_caddy_processes(self) -> List[int]:
        """
        Find all Caddy processes
        
        Returns:
            List of PIDs
        """
        pids = []
        our_caddy_path = str(self.caddy_path)
        
        try:
            # First try ps with our specific binary path to find only our caddy processes
            ps_cmd = ["ps", "-eo", "pid,command"]
            ps_result = subprocess.run(ps_cmd, capture_output=True, text=True, check=False)
            
            if ps_result.returncode == 0:
                for line in ps_result.stdout.strip().split('\n'):
                    parts = line.strip().split(None, 1)
                    if len(parts) < 2:
                        continue
                    
                    pid_str, cmd = parts
                    # Look specifically for our Caddy binary path and ensure "run" is in the command
                    if our_caddy_path in cmd and "run" in cmd:
                        try:
                            pids.append(int(pid_str))
                            logger.debug(f"Found Caddy process: PID={pid_str}, CMD={cmd}")
                        except ValueError:
                            continue
            
            if not pids:
                # Try a more generic search if our specific search fails
                ps_cmd = ["ps", "-eo", "pid,command"]
                ps_result = subprocess.run(ps_cmd, capture_output=True, text=True, check=False)
                
                if ps_result.returncode == 0:
                    for line in ps_result.stdout.strip().split('\n'):
                        parts = line.strip().split(None, 1)
                        if len(parts) < 2:
                            continue
                        
                        pid_str, cmd = parts
                        # Look for any caddy binary with 'run' command
                        if "caddy" in cmd and "run" in cmd:
                            try:
                                pids.append(int(pid_str))
                                logger.debug(f"Found Caddy process (generic search): PID={pid_str}, CMD={cmd}")
                            except ValueError:
                                continue
                
                # Fallback to pgrep
                if not pids:
                    # Fallback to pgrep but be very specific
                    # Look for full command path to avoid finding unrelated processes
                    pgrep_cmd = ["pgrep", "-f", f"{our_caddy_path} run"]
                    pgrep_result = subprocess.run(pgrep_cmd, capture_output=True, text=True, check=False)
                    
                    if pgrep_result.returncode == 0:
                        for pid_str in pgrep_result.stdout.strip().split('\n'):
                            if pid_str.strip():
                                try:
                                    pid = int(pid_str.strip())
                                    # Double check the command to ensure it's our caddy
                                    check_cmd = ["ps", "-p", str(pid), "-o", "command", "--no-headers"]
                                    check_result = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
                                    
                                    if check_result.returncode == 0 and our_caddy_path in check_result.stdout and "run" in check_result.stdout:
                                        pids.append(pid)
                                        logger.debug(f"Found Caddy process via pgrep: PID={pid}, CMD={check_result.stdout.strip()}")
                                except ValueError:
                                    continue
                    
                    # More generic pgrep as last resort
                    if not pids:
                        pgrep_cmd = ["pgrep", "-f", "caddy run"]
                        pgrep_result = subprocess.run(pgrep_cmd, capture_output=True, text=True, check=False)
                        
                        if pgrep_result.returncode == 0:
                            for pid_str in pgrep_result.stdout.strip().split('\n'):
                                if pid_str.strip():
                                    try:
                                        pid = int(pid_str.strip())
                                        pids.append(pid)
                                        logger.debug(f"Found Caddy process via generic pgrep: PID={pid}")
                                    except ValueError:
                                        continue
            
            logger.info(f"Found {len(pids)} Caddy processes: {pids}")
            return pids
            
        except Exception as e:
            logger.error(f"Error while searching for Caddy processes: {e}")
            return []
    
    def _kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process by PID"""
        if not self._is_process_running(pid):
            logger.info(f"Process {pid} not running")
            return True
            
        try:
            if force:
                # Force kill with SIGKILL
                logger.info(f"Force killing process {pid} with SIGKILL")
                os.kill(pid, signal.SIGKILL)
            else:
                # Try graceful shutdown with SIGTERM first
                logger.info(f"Gracefully stopping process {pid} with SIGTERM")
                os.kill(pid, signal.SIGTERM)
                
                # Wait for process to terminate
                for _ in range(10):  # 5 seconds
                    if not self._is_process_running(pid):
                        logger.info(f"Process {pid} terminated gracefully")
                        return True
                    time.sleep(0.5)
                    
                # If still running, force kill
                logger.warning(f"Process {pid} didn't terminate gracefully, using SIGKILL")
                os.kill(pid, signal.SIGKILL)
            
            # Wait to confirm process is gone
            time.sleep(1)
            if self._is_process_running(pid):
                logger.error(f"Failed to kill process {pid}")
                return False
                
            logger.info(f"Process {pid} terminated")
            return True
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            return False
    
    def _get_cloudflare_auth_config(self) -> Dict[str, str]:
        """Get Cloudflare authentication configuration"""
        # Check if zone and DNS tokens are available
        if self.config.cloudflare_zone_token and self.config.cloudflare_dns_token:
            logger.info("Using Cloudflare Zone and DNS Tokens for authentication (least privilege)")
            # Use environment variables for tokens
            return {
                'cloudflare_auth': "{env.CLOUDFLARE_DNS_TOKEN}",
                'acme_dns_auth': 'acme_dns cloudflare {env.CLOUDFLARE_DNS_TOKEN}'
            }
        
        # Fall back to API token
        if self.config.cloudflare_token:
            logger.info("Using Cloudflare API Token for authentication")
            return {
                'cloudflare_auth': "{env.CLOUDFLARE_API_TOKEN}",
                'acme_dns_auth': 'acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}'
            }
        
        # Fall back to global API key (legacy)
        logger.info("Using Cloudflare Global API Key for authentication (legacy)")
        return {
            'cloudflare_auth': "{env.CLOUDFLARE_API_KEY} {env.CLOUDFLARE_EMAIL}",
            'acme_dns_auth': 'acme_dns cloudflare {env.CLOUDFLARE_API_KEY} {env.CLOUDFLARE_EMAIL}'
        }
    
    def generate_config(self, domain=None, target: str = None) -> str:
        """
        Generate Caddy configuration
        
        Args:
            domain: Domain to proxy (string or ProxyConfig object)
            target: Target to proxy to (optional)
        
        Returns:
            Generated configuration
        """
        try:
            # Get Cloudflare authentication configuration
            cloudflare_auth = self._get_cloudflare_auth_config()
            
            # Extract domain and target information
            domain_to_use = None
            target_to_use = None
            
            # Check if domain is a ProxyConfig object
            if isinstance(domain, ProxyConfig):
                logger.debug(f"Processing ProxyConfig object: {domain}")
                domain_to_use = domain.domain
                target_to_use = domain.target
            else:
                # Use domain and target from parameters or config
                domain_to_use = domain or self.config.domain
                target_to_use = target or "localhost:8080"  # Default target
            
            logger.info(f"Generating config for domain: {domain_to_use}, target: {target_to_use}")
            
            # Generate the global configuration if Caddyfile doesn't exist
            if not self.caddyfile_path.exists():
                # Generate global configuration
                global_config = self.parser.generate_config(
                    email=self.config.email,
                    data_dir=str(self.dirs['data']),
                    acme_dns_auth=cloudflare_auth.get('acme_dns_auth', '')
                )
                
                # Initialize parser with global config
                self.parser._parse_content(global_config)
            
            # If domain is specified, create/update the site block
            if domain_to_use:
                logger.info(f"Generating site block for domain: {domain_to_use}")
                
                # Create logs directory
                logs_dir = self.dirs['data'] / 'logs'
                logs_dir.mkdir(parents=True, exist_ok=True)
                self.dirs['logs'] = logs_dir
                
                # Set up log path
                log_path = logs_dir / f"{domain_to_use}.log"
                
                # Create or update the site block
                success = self.parser.create_or_update_site(
                    domain=domain_to_use,  # Now we're passing a string, not a ProxyConfig
                    target=target_to_use,
                    cloudflare_auth=cloudflare_auth.get('cloudflare_auth', ''),
                    log_path=str(log_path)
                )
                
                if not success:
                    logger.warning(f"Failed to create or update site block for {domain_to_use}")
            
            # Save Caddyfile
            logger.info(f"Saving Caddyfile to: {self.caddyfile_path}")
            self.parser.save(str(self.caddyfile_path))
            
            # Return the path to the Caddyfile, not its contents
            return str(self.caddyfile_path)
            
        except Exception as e:
            logger.error(f"Failed to generate configuration: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def validate_config_content(self, content: str) -> bool:
        """
        Validate Caddy configuration content
        
        Args:
            content: Configuration content to validate
            
        Returns:
            True if valid
        """
        # Log that we're validating content without printing the entire content
        content_preview = content[:50] + "..." if len(content) > 50 else content
        logger.info(f"Validating configuration content (preview): {content_preview}")
        
        import tempfile
        
        # Create a temporary file with the configuration content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.caddyfile', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(content)
        
        try:
            # Validate the temporary file
            result = self.validate_config(tmp_path)
            return result
        finally:
            # Clean up the temporary file
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {tmp_path}: {e}")
                    
    def validate_config(self, config_file: Optional[Union[Path, str]] = None) -> bool:
        """
        Validate Caddy configuration
        
        Args:
            config_file: Path to config file to validate or config content
            
        Returns:
            True if valid
        """
        # Default to the Caddyfile path
        if config_file is None:
            file_to_validate = self.caddyfile_path
            logger.info(f"Validating default Caddyfile at {file_to_validate}")
        else:
            # Check if it's a string path or content
            if isinstance(config_file, str):
                # If it's a short string and exists as a file, treat as path
                if len(config_file) < 255 and Path(config_file).exists():
                    file_to_validate = Path(config_file)
                    logger.info(f"Validating Caddyfile at {file_to_validate}")
                else:
                    # It's likely content, not a path
                    logger.info("Validating provided configuration content")
                    return self.validate_config_content(config_file)
            else:
                # It's a Path object
                file_to_validate = config_file
                logger.info(f"Validating Caddyfile at {file_to_validate}")
        
        try:
            # Make sure the file exists before validating
            if not file_to_validate.exists():
                logger.error(f"Config file does not exist: {file_to_validate}")
                return False
                
            # Validate configuration with caddy
            result = subprocess.run(
                [str(self.caddy_path), 'validate', '--config', str(file_to_validate)],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("Configuration validation successful")
                return True
            
            logger.error(f"Configuration validation failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def _verify_process_binding(self, pid: int, port: int) -> bool:
        """
        Verify if a process is binding to a specific port
        
        Args:
            pid: Process ID
            port: Port number
            
        Returns:
            True if process is binding to the port
        """
        if not self._is_process_running(pid):
            logger.debug(f"Process {pid} is not running")
            return False
            
        try:
            # Try multiple methods to verify port binding
            
            # Method 1: Use lsof to check if the process is listening on the port
            cmd = ["lsof", "-i", f":{port}", "-P", "-n", "-p", str(pid)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Parse the output to look for LISTEN state
            if result.returncode == 0 and "LISTEN" in result.stdout:
                logger.debug(f"Process {pid} is binding to port {port}")
                return True
            
            # Method 2: More general lsof check (don't filter by pid)
            cmd = ["lsof", "-i", f":{port}", "-P", "-n"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Parse the output to look for our PID and LISTEN state
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if str(pid) in line and "LISTEN" in line:
                        logger.debug(f"Process {pid} is binding to port {port} (general lsof)")
                        return True
                
            # Method 3: If lsof is successful but no LISTEN state, check netstat
            cmd = ["netstat", "-tulpn"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            for line in result.stdout.split("\n"):
                if f":{port}" in line and f"{pid}/" in line and "LISTEN" in line:
                    logger.debug(f"Process {pid} is binding to port {port} (verified by netstat)")
                    return True
                    
            # Method 4: Try ss command as a last resort
            cmd = ["ss", "-tulpn"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            for line in result.stdout.split("\n"):
                if f":{port}" in line and f"pid={pid}" in line:
                    logger.debug(f"Process {pid} is binding to port {port} (verified by ss)")
                    return True
                
            # Method 5: Check if any process is using the port
            # This is a fallback when we can't reliably associate a PID with the port
            cmd = ["lsof", "-i", f":{port}", "-P", "-n"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and "LISTEN" in result.stdout:
                # Port is in use, but we couldn't verify it's our process
                logger.warning(f"Port {port} is in use, but couldn't confirm it's by process {pid}")
                logger.warning(f"lsof output: {result.stdout}")
                # Return false here as we want to ensure it's our process
                return False
                    
            logger.debug(f"Process {pid} is not binding to port {port}")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying process binding: {e}")
            # If we can't check, assume it's not binding
            return False
    
    def start(self, config_file: Optional[Union[Path, str]] = None) -> ProxyStatus:
        """
        Start the proxy server
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            ProxyStatus object
            
        Raises:
            ProxyError: If server fails to start
        """
        # Check if already running
        if self.is_running():
            logger.info("Caddy is already running")
            pid = self._get_pid()
            return ProxyStatus(
                running=True,
                pid=pid,
                config_file=self.caddyfile_path,
                error=None
            )
        
        # Stop any existing Caddy processes that might be running but not properly detected
        caddy_pids = self._find_caddy_processes()
        if caddy_pids:
            logger.warning(f"Found {len(caddy_pids)} existing Caddy processes that weren't properly detected. Stopping them first.")
            for pid in caddy_pids:
                self._kill_process(pid, force=True)
            time.sleep(1)  # Give processes time to fully terminate
            
            # Verify they're really gone
            if self._find_caddy_processes():
                logger.error("Failed to stop existing Caddy processes. This might cause conflicts.")
        
        # Check if the required ports are already in use
        if self._is_port_in_use(443):
            logger.error("Port 443 is already in use. Cannot start Caddy.")
            logger.error("Use 'lsof -i :443 -P -n' to see which process is using port 443")
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=None,
                error="Port 443 is already in use"
            )
        
        # Check if Caddy is installed by systemd and running
        try:
            systemctl_result = subprocess.run(
                ["systemctl", "is-active", "caddy"],
                capture_output=True,
                text=True,
                check=False
            )
            if systemctl_result.stdout.strip() == "active":
                logger.error("Caddy is already running as a systemd service.")
                logger.error("Please stop the systemd service first: sudo systemctl stop caddy")
                return ProxyStatus(
                    running=False,
                    pid=None,
                    config_file=None,
                    error="Caddy is already running as a systemd service"
                )
        except Exception:
            # Ignore errors if systemctl is not available
            pass
            
        # Determine the configuration file to use
        file_to_use = config_file or self.caddyfile_path
        
        # Make sure we have a Path object if it's a file path
        if isinstance(file_to_use, str) and len(file_to_use) < 255 and Path(file_to_use).exists():
            file_to_use = Path(file_to_use)
            
        # Validate configuration
        if not self.validate_config(file_to_use):
            logger.error("Cannot start server with invalid configuration")
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=None,
                error="Cannot start server with invalid configuration"
            )
        
        # Set up environment variables for Cloudflare authentication
        env = os.environ.copy()
        
        # Determine which credentials to use based on available config
        if self.config.cloudflare_zone_token and self.config.cloudflare_dns_token:
            logger.info("Using Zone and DNS tokens for Caddy authentication")
            env['CLOUDFLARE_DNS_TOKEN'] = self.config.cloudflare_dns_token
        elif self.config.cloudflare_token:
            logger.info("Using API Token for Caddy authentication")
            env['CLOUDFLARE_API_TOKEN'] = self.config.cloudflare_token
        else:
            logger.info("Using Global API Key for Caddy authentication")
            env['CLOUDFLARE_API_KEY'] = self.config.cloudflare_api_key
            env['CLOUDFLARE_EMAIL'] = self.config.cloudflare_api_email
        
        try:
            # Prepare log directory
            log_dir = self.dirs['data'] / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / 'caddy.log'
            
            # Ensure port 443 is free before starting
            if self._is_port_in_use(443):
                logger.error("Port 443 is now in use by another process. Cannot start Caddy.")
                try:
                    lsof_result = subprocess.run(
                        ["lsof", "-i", ":443", "-P", "-n"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if lsof_result.stdout:
                        logger.error(f"Port 443 is being used by:\n{lsof_result.stdout}")
                except Exception:
                    pass
                return ProxyStatus(
                    running=False,
                    pid=None,
                    config_file=None,
                    error="Port 443 is already in use"
                )
                
            # Build the start command - this is the most reliable way to start Caddy in background
            # We're using nohup and shell=True to ensure the process stays alive
            start_cmd = f"nohup {self.caddy_path} run --config {file_to_use} > {log_file} 2>&1 & echo $!"
            logger.info(f"Starting Caddy with command: {start_cmd}")
            
            # Execute the command
            process = subprocess.run(
                start_cmd,
                shell=True,
                env=env,
                text=True,
                capture_output=True
            )
            
            if process.returncode != 0:
                logger.error(f"Failed to start Caddy: {process.stderr}")
                return ProxyStatus(
                    running=False,
                    pid=None,
                    config_file=None,
                    error=f"Failed to start Caddy: {process.stderr}"
                )
                
            # Get the PID from the output
            pid = process.stdout.strip()
            if not pid:
                logger.error("Failed to get PID after starting Caddy")
                return ProxyStatus(
                    running=False,
                    pid=None,
                    config_file=None,
                    error="Failed to get PID after starting Caddy"
                )
                
            pid = int(pid)
            logger.info(f"Started Caddy process with PID {pid}")
            self._save_pid(pid)
            
            # Wait for Caddy to start up (30 seconds max)
            logger.info(f"Waiting for Caddy (PID {pid}) to bind to port 443...")
            max_attempts = 15
            for attempt in range(1, max_attempts + 1):
                time.sleep(2)
                
                # Check if process is still running
                if not self._is_process_running(pid):
                    logger.error(f"Caddy process stopped unexpectedly (PID {pid})")
                    # Try to get last lines of log
                    self._show_log_tail(log_file)
                    return ProxyStatus(
                        running=False,
                        pid=None,
                        config_file=None,
                        error="Caddy process stopped unexpectedly"
                    )
                
                # Check if port 443 is in use by our process
                if self._verify_process_binding(pid, 443):
                    logger.info(f"Caddy server (PID {pid}) started successfully and bound to port 443")
                    return ProxyStatus(
                        running=True,
                        pid=pid,
                        config_file=self.caddyfile_path if isinstance(config_file, Path) else Path(config_file),
                        error=None
                    )
                
                # Check if another Caddy process has started and is binding to port 443
                other_caddy_pids = [p for p in self._find_caddy_processes() if p != pid]
                for other_pid in other_caddy_pids:
                    if self._verify_process_binding(other_pid, 443):
                        logger.info(f"Another Caddy process (PID {other_pid}) is binding to port 443")
                        # Update our PID file
                        self._save_pid(other_pid)
                        # Terminate the original process
                        self._kill_process(pid, force=True)
                        return ProxyStatus(
                            running=True,
                            pid=other_pid,
                            config_file=self.caddyfile_path if isinstance(config_file, Path) else Path(config_file),
                            error=None
                        )
                
                logger.debug(f"Waiting for Caddy to bind to port 443 (attempt {attempt}/{max_attempts})...")
            
            # Process is still running but not bound to port 443
            logger.error(f"Caddy process is running but not bound to port 443 after {max_attempts * 2} seconds")
            
            # Show log file and what's using port 443
            self._show_log_tail(log_file)
            
            # Check if port 443 is in use by another program
            self._show_port_usage(443)
            
            # Check if the Caddy process is using any ports
            try:
                lsof_pid_result = subprocess.run(
                    ["lsof", "-i", "-P", "-n", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if lsof_pid_result.returncode == 0 and lsof_pid_result.stdout:
                    logger.info(f"Caddy process {pid} is using these network connections:")
                    logger.info(lsof_pid_result.stdout)
            except Exception as e:
                logger.error(f"Error checking Caddy network connections: {e}")
                
            # Last attempt: check if Caddy is running and just return success
            # This allows Caddy to continue running even if we can't verify port binding,
            # as sometimes Caddy works even when port binding checks fail
            if self._is_process_running(pid):
                logger.warning("Caddy is running but port binding verification failed. Continuing anyway.")
                return ProxyStatus(
                    running=True,
                    pid=pid,
                    config_file=self.caddyfile_path if isinstance(config_file, Path) else Path(config_file),
                    error=None
                )
                
            # Kill the process since it's not working properly
            logger.warning(f"Terminating non-functional Caddy process (PID {pid})")
            self._kill_process(pid, force=True)
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=None,
                error="Caddy process is not working properly"
            )
            
        except Exception as e:
            logger.error(f"Error starting Caddy server: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=None,
                error=f"Error starting Caddy server: {e}"
            )
            
    def _show_log_tail(self, log_file: Path, lines: int = 20):
        """Show the last lines of a log file"""
        if not log_file.exists():
            logger.error(f"Log file does not exist: {log_file}")
            return
            
        try:
            with open(log_file, 'r') as f:
                log_content = f.readlines()
                last_lines = log_content[-lines:] if len(log_content) > lines else log_content
                log_excerpt = ''.join(last_lines)
                logger.error(f"Last {len(last_lines)} lines from log file:\n{log_excerpt}")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            
    def _show_port_usage(self, port: int):
        """Show what process is using a specific port"""
        try:
            lsof_result = subprocess.run(
                ["lsof", "-i", f":{port}", "-P", "-n"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if lsof_result.returncode == 0 and lsof_result.stdout:
                logger.error(f"Port {port} is being used by:\n{lsof_result.stdout}")
            else:
                logger.error(f"No process found using port {port}")
        except Exception as e:
            logger.error(f"Error checking port usage: {e}")
    
    def stop(self) -> bool:
        """
        Stop Caddy server
        
        Returns:
            True if stopped successfully or not running
        """
        # Check if Caddy is running
        if not self.is_running():
            logger.info("Caddy is not running")
            return True
            
        # Get all Caddy processes
        caddy_pids = self._find_caddy_processes()
        success = True
        
        if caddy_pids:
            logger.info(f"Found {len(caddy_pids)} Caddy processes to stop")
            for pid in caddy_pids:
                try:
                    # Try graceful stop first
                    if self._kill_process(pid, force=False):
                        logger.info(f"Gracefully stopped Caddy process with PID {pid}")
                    else:
                        # Force kill if graceful stop fails
                        logger.warning(f"Graceful stop failed, force killing Caddy process with PID {pid}")
                        if self._kill_process(pid, force=True):
                            logger.info(f"Force killed Caddy process with PID {pid}")
                        else:
                            logger.error(f"Failed to kill Caddy process with PID {pid}")
                            success = False
                except Exception as e:
                    logger.error(f"Error stopping Caddy process with PID {pid}: {e}")
                    success = False
                    
            # Wait a moment to ensure processes are fully stopped
            time.sleep(1)
            
            # Check if any processes are still running
            remaining_pids = self._find_caddy_processes()
            if remaining_pids:
                logger.error(f"Some Caddy processes are still running: {remaining_pids}")
                for pid in remaining_pids:
                    # One last attempt to force kill
                    self._kill_process(pid, force=True)
                
                # Final check
                if self._find_caddy_processes():
                    logger.error("Failed to stop all Caddy processes")
                    success = False
        
        # Clean up PID file
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info("Removed PID file")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")
        
        return success
    
    def status(self) -> ProxyStatus:
        """
        Check if Caddy is running
        
        Returns:
            ProxyStatus object with running status and process info
        """
        # Try to get the PID from the PID file
        pid = self._get_pid()
        
        # If we have a PID, check if that process is running
        if pid and self._is_process_running(pid):
            # Check if it's actually a Caddy process by examining the command
            try:
                cmd_result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "cmd", "--no-headers"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if cmd_result.returncode == 0:
                    process_cmd = cmd_result.stdout.strip()
                    caddy_path_str = str(self.caddy_path)
                    
                    # Check if the process is our Caddy binary and has 'run' command
                    if caddy_path_str in process_cmd and "run" in process_cmd:
                        logger.debug(f"Process {pid} is a Caddy process: {process_cmd}")
                        return ProxyStatus(
                            running=True, 
                            pid=pid, 
                            config_file=self.caddyfile_path,
                            error=None
                        )
                    else:
                        logger.warning(f"PID {pid} exists but is not a Caddy process: {process_cmd}")
            except Exception as e:
                logger.error(f"Error checking process command: {e}")
        
        # If we don't have a valid PID or the PID isn't running, 
        # search for Caddy processes
        caddy_pids = self._find_caddy_processes()
        
        if caddy_pids:
            # Update the PID file with the first found Caddy process
            self._save_pid(caddy_pids[0])
            return ProxyStatus(
                running=True, 
                pid=caddy_pids[0], 
                config_file=self.caddyfile_path,
                error=None
            )
        
        return ProxyStatus(
            running=False, 
            pid=None, 
            config_file=None,
            error="No running Caddy process found"
        )
    
    def reload(self) -> bool:
        """
        Reload Caddy configuration
        
        Returns:
            True if reloaded successfully
        """
        # Validate the configuration file path, not its content
        if not self.validate_config(self.caddyfile_path):
            logger.error("Cannot reload with invalid configuration")
            return False
        
        # Check if Caddy is running
        if not self.is_running():
            logger.warning("Caddy is not running, starting instead of reloading")
            return self.start()
        
        pid = self._get_pid()
        if pid and self._is_process_running(pid):
            try:
                # Send SIGHUP to reload configuration
                logger.info(f"Sending SIGHUP to PID {pid} to reload configuration")
                os.kill(pid, signal.SIGHUP)
                
                # Wait a moment to verify Caddy is still running
                time.sleep(1)
                if self._is_process_running(pid):
                    logger.info("Caddy configuration reloaded")
                    return True
                else:
                    logger.error("Caddy process stopped after reload")
            except Exception as e:
                logger.error(f"Error reloading Caddy: {e}")
        
        logger.error("No running Caddy process found for reload")
        return False

    def install(self, system_wide: bool = False) -> bool:
        """
        Install Caddy binary
        
        Args:
            system_wide: Whether to install system-wide (requires sudo)
            
        Returns:
            True if successful
            
        Raises:
            ProxyError: If installation fails
        """
        try:
            # Create bin directory if it doesn't exist
            bin_dir = self.dirs['bin']
            bin_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine target path
            target_path = Path("/usr/local/bin/caddy") if system_wide else self.caddy_path
            
            # Check if Caddy is already installed
            caddy_exists = target_path.exists()
            if caddy_exists:
                logger.info(f"Caddy is already installed at {target_path}")
                return True
                
            # Determine platform and architecture
            import platform
            system = platform.system().lower()
            machine = platform.machine().lower()
            
            arch_map = {
                'x86_64': 'amd64',
                'amd64': 'amd64',
                'aarch64': 'arm64',
                'arm64': 'arm64',
                'armv7l': 'arm',
                'armv6l': 'arm'
            }
            
            os_map = {
                'darwin': 'mac',
                'linux': 'linux',
                'windows': 'windows'
            }
            
            os_name = os_map.get(system, system)
            arch = arch_map.get(machine, machine)
            
            # Determine file extension
            ext = '.exe' if os_name == 'windows' else ''
            
            # Download URL - using custom URL instead of dynamic construction
            download_url = "https://github.com/tadeasf/caddy_cloudflare_cli/releases/download/v0.10.0/caddy-cloudflare-linux-amd6"
            
            logger.info(f"Downloading Caddy from {download_url}")
            
            # Use requests to download the file
            import requests
            from rich.progress import Progress, TransferSpeedColumn, DownloadColumn
            
            headers = {'User-Agent': 'caddy-cloudflare-cli/1.0'}
            
            with requests.get(download_url, stream=True, headers=headers, timeout=30) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                # Create temporary file path
                temp_path = bin_dir / f"caddy_temp{ext}"
                
                # Download with progress bar
                with open(temp_path, 'wb') as f:
                    with Progress(
                        TransferSpeedColumn(),
                        DownloadColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                    ) as progress:
                        task = progress.add_task("Downloading Caddy", total=total_size)
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
                
                # Make the file executable
                if os_name != 'windows':
                    temp_path.chmod(0o755)
                
                # Move to final location
                if system_wide:
                    logger.info("Installing Caddy system-wide (requires sudo)")
                    result = subprocess.run(
                        ["sudo", "mv", str(temp_path), str(target_path)],
                        check=False
                    )
                    if result.returncode != 0:
                        logger.error(f"Failed to install Caddy system-wide: {result.stderr}")
                        return False
                else:
                    # For user install, just rename the file
                    temp_path.rename(target_path)
                    
                logger.info(f"Caddy installed successfully at {target_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to install Caddy: {e}")
            return False
    
    def uninstall(self) -> bool:
        """
        Uninstall Caddy binary
        
        Returns:
            True if successful
            
        Raises:
            ProxyError: If uninstallation fails
        """
        try:
            # Stop Caddy if it's running
            if self.is_running():
                logger.info("Stopping Caddy before uninstalling")
                self.stop()
                
            # Remove Caddy binary
            if self.caddy_path.exists():
                logger.info(f"Removing Caddy binary at {self.caddy_path}")
                self.caddy_path.unlink()
                
            # Check if it was successfully removed
            if self.caddy_path.exists():
                logger.error(f"Failed to remove Caddy binary at {self.caddy_path}")
                return False
                
            logger.info("Caddy uninstalled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall Caddy: {e}")
            return False

    # Method used by other functions to check if Caddy is running
    def is_running(self) -> bool:
        """Helper method to check if Caddy is running"""
        return self.status().running
