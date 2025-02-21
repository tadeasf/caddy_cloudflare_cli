"""
Caddy reverse proxy implementation
"""
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, List
import requests
import logging

from ..config import Config
from .base import ReverseProxy, ProxyConfig, ProxyStatus, ProxyError

logger = logging.getLogger(__name__)

class CaddyProxy(ReverseProxy):
    """Caddy reverse proxy implementation"""
    
    def __init__(self, config: Config):
        """Initialize Caddy proxy"""
        self.config = config
        self.binary_path = config.get_binary_path()
        
        # Ensure directories exist
        self.dirs = config.get_proxy_dirs()
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
            
        self._process = None
        self._pid_file = self.dirs['data'] / 'caddy.pid'
        
        # Try to restore existing process
        self._restore_process()
    
    def _restore_process(self):
        """Try to restore existing Caddy process"""
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                self._process = subprocess.Popen(
                    pid=pid,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                logger.info(f"Restored Caddy process with PID {pid}")
            except (ProcessLookupError, ValueError):
                self._pid_file.unlink(missing_ok=True)
    
    def _save_pid(self):
        """Save process PID to file"""
        if self._process and self._process.pid:
            self._pid_file.write_text(str(self._process.pid))
    
    def generate_config(self, config: ProxyConfig) -> str:
        """Generate Caddy configuration"""
        try:
            # Basic Caddyfile configuration
            caddy_config = f"""{{
    # Global options
    admin off  # Disable admin API for security
    auto_https disable_redirects  # Let Cloudflare handle HTTPS redirects
    
    # Storage configuration
    storage file_system {{
        root {self.dirs['data']}
    }}
    
    # Cloudflare DNS challenge
    acme_dns cloudflare {{env.CF_API_TOKEN}}
}}

{config.domain} {{
    reverse_proxy {config.target} {{
        # Health checks
        health_uri /health
        health_interval 30s
        health_timeout 10s
        
        # Timeouts
        timeout 30s
        
        # Headers
        header_up Host {config.domain}
        header_up X-Real-IP {{remote_host}}
        header_up X-Forwarded-For {{remote_host}}
        header_up X-Forwarded-Proto {{scheme}}
    }}
    
    tls {{
        dns cloudflare {{env.CF_API_TOKEN}}
    }}
    
    # Logging
    log {{
        output file {self.dirs['data']}/access.log {{
            roll_size 10MB
            roll_keep 10
        }}
        format json
    }}
    
    # Security headers
    header {{
        # Enable HSTS
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        # Prevent clickjacking
        X-Frame-Options "SAMEORIGIN"
        # XSS protection
        X-Content-Type-Options "nosniff"
        X-XSS-Protection "1; mode=block"
        # Referrer policy
        Referrer-Policy "strict-origin-when-cross-origin"
    }}
"""

            # Add any additional configuration
            if config.additional_config:
                for key, value in config.additional_config.items():
                    caddy_config += f"    {key} {value}\n"
                    
            caddy_config += "}\n"
            
            # Write configuration to file
            config_path = self.dirs['config'] / 'Caddyfile'
            config_path.write_text(caddy_config)
            logger.info(f"Generated Caddy configuration at {config_path}")
                
            return str(config_path)
            
        except Exception as e:
            raise ProxyError(f"Failed to generate configuration: {str(e)}")
    
    def validate_config(self, config_str: str) -> bool:
        """Validate Caddy configuration"""
        try:
            if not Path(config_str).exists():
                raise ProxyError(f"Configuration file not found: {config_str}")
                
            result = subprocess.run(
                [str(self.binary_path), 'validate', '-config', config_str],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Configuration validation successful")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Configuration validation failed: {e.stderr}")
            return False
        except Exception as e:
            raise ProxyError(f"Failed to validate configuration: {str(e)}")
    
    def start(self, config_file: Path) -> ProxyStatus:
        """Start Caddy server"""
        try:
            # Stop if already running
            self.stop()
            
            # Validate configuration first
            if not self.validate_config(str(config_file)):
                raise ProxyError("Invalid configuration")
            
            # Prepare environment
            env = os.environ.copy()
            env['CF_API_TOKEN'] = self.config.cloudflare_token
            
            # Start Caddy with proper logging
            self._process = subprocess.Popen(
                [
                    str(self.binary_path),
                    'run',
                    '-config', str(config_file),
                    '-pidfile', str(self._pid_file)
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent process
            )
            
            # Wait for startup
            time.sleep(2)  # Give Caddy time to start
            
            # Check if started successfully
            if self._process.poll() is not None:
                error = self._process.stderr.read().decode('utf-8')
                raise ProxyError(f"Failed to start Caddy: {error}")
            
            # Save PID
            self._save_pid()
            
            logger.info(f"Started Caddy server with PID {self._process.pid}")
            return ProxyStatus(
                running=True,
                pid=self._process.pid,
                config_file=Path(config_file),
                error=None
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to start Caddy: {error_msg}")
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=Path(config_file),
                error=error_msg
            )
    
    def stop(self) -> bool:
        """Stop Caddy server"""
        if not self._process:
            return True
            
        try:
            # Try graceful shutdown first
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                self._process.kill()
                self._process.wait(timeout=5)
            
            # Clean up PID file
            self._pid_file.unlink(missing_ok=True)
            
            logger.info("Stopped Caddy server")
            return True
            
        except Exception as e:
            raise ProxyError(f"Failed to stop Caddy: {str(e)}")
        finally:
            self._process = None
    
    def reload(self) -> bool:
        """Reload Caddy configuration"""
        if not self._process or self._process.poll() is not None:
            raise ProxyError("Caddy is not running")
            
        try:
            # Send SIGHUP for config reload
            self._process.send_signal(signal.SIGHUP)
            
            # Wait briefly and check if process is still running
            time.sleep(1)
            if self._process.poll() is not None:
                raise ProxyError("Caddy stopped during reload")
            
            logger.info("Reloaded Caddy configuration")
            return True
            
        except Exception as e:
            raise ProxyError(f"Failed to reload Caddy: {str(e)}")
    
    def status(self) -> ProxyStatus:
        """Get Caddy status"""
        running = False
        error = None
        pid = None
        
        try:
            if self._process:
                # Check if process is still running
                if self._process.poll() is None:
                    running = True
                    pid = self._process.pid
                else:
                    error = self._process.stderr.read().decode('utf-8')
                    self._process = None
                    self._pid_file.unlink(missing_ok=True)
            
            return ProxyStatus(
                running=running,
                pid=pid,
                config_file=self.dirs['config'] / 'Caddyfile',
                error=error
            )
            
        except Exception as e:
            logger.error(f"Failed to get Caddy status: {str(e)}")
            return ProxyStatus(
                running=False,
                pid=None,
                config_file=self.dirs['config'] / 'Caddyfile',
                error=str(e)
            )
    
    def install(self, system_wide: bool = False) -> bool:
        """Install Caddy binary"""
        try:
            # Get system info
            from ..utils import get_system_info
            os_type, arch = get_system_info()
            
            # Download URL
            version = "v2.7.6"  # Latest stable version
            binary_name = f"caddy-cloudflare-{os_type}-{arch}"
            url = f"https://github.com/tadeasf/caddy-cloudflare-cli/releases/download/{version}/{binary_name}"
            
            # Create binary directory
            self.binary_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download binary
            from ..utils import download_file
            if not download_file(url, self.binary_path):
                raise ProxyError("Failed to download Caddy binary")
            
            # Make executable
            self.binary_path.chmod(0o755)
            
            # Create symlink if system-wide
            if system_wide:
                symlink = Path('/usr/local/bin/caddy')
                if symlink.exists():
                    symlink.unlink()
                symlink.symlink_to(self.binary_path)
            
            logger.info(f"Installed Caddy binary at {self.binary_path}")
            return True
            
        except Exception as e:
            raise ProxyError(f"Failed to install Caddy: {str(e)}")
    
    def uninstall(self) -> bool:
        """Uninstall Caddy"""
        try:
            # Stop if running
            self.stop()
            
            # Remove binary
            if self.binary_path.exists():
                self.binary_path.unlink()
            
            # Remove system-wide symlink
            symlink = Path('/usr/local/bin/caddy')
            if symlink.exists() and symlink.is_symlink():
                symlink.unlink()
            
            # Remove directories
            for dir_path in self.dirs.values():
                if dir_path.exists():
                    import shutil
                    shutil.rmtree(dir_path)
            
            logger.info("Uninstalled Caddy")
            return True
            
        except Exception as e:
            raise ProxyError(f"Failed to uninstall Caddy: {str(e)}")
