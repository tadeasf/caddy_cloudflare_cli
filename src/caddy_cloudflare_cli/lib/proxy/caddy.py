"""
Caddy reverse proxy implementation
"""
import os
import signal
import subprocess
import time
from pathlib import Path
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
            except (ProcessLookupError, ValueError, OSError):
                self._pid_file.unlink(missing_ok=True)
    
    def _save_pid(self):
        """Save process PID to file"""
        if self._process and self._process.pid:
            self._pid_file.write_text(str(self._process.pid))
    
    def generate_config(self, config: ProxyConfig) -> str:
        """Generate Caddy configuration"""
        try:
            # Determine which Cloudflare auth method to use
            has_valid_token = bool(self.config.cloudflare_token and self.config.cloudflare_token.strip())
            has_valid_api_key = bool(self.config.cloudflare_api_key and self.config.cloudflare_api_email and 
                                    self.config.cloudflare_api_key.strip() and self.config.cloudflare_api_email.strip())
            has_valid_dual_tokens = bool(self.config.cloudflare_zone_token and self.config.cloudflare_dns_token and
                                    self.config.cloudflare_zone_token.strip() and self.config.cloudflare_dns_token.strip())
            
            if has_valid_dual_tokens:
                # Use separate Zone and DNS tokens (preferred for least privilege)
                logger.info("Using separate Zone and DNS tokens for Caddy (least privilege)")
                cloudflare_auth = "{\n            zone_token {env.CLOUDFLARE_ZONE_TOKEN}\n            api_token {env.CLOUDFLARE_DNS_TOKEN}\n        }"
            elif has_valid_token:
                # Token-based authentication (API token only)
                logger.info("Using API Token authentication for Caddy")
                cloudflare_auth = "{env.CLOUDFLARE_API_TOKEN}"
            elif has_valid_api_key:
                # Global API Key authentication
                logger.info("Using Global API Key authentication for Caddy")
                cloudflare_auth = "{\n            api_key {env.CLOUDFLARE_EMAIL} {env.CLOUDFLARE_API_KEY}\n        }"
            else:
                raise ProxyError("No valid Cloudflare authentication method configured")
            
            # Basic Caddyfile configuration
            caddy_config = f"""{{
    # Global options
    admin off  # Disable admin API for security
    auto_https disable_redirects  # Let Cloudflare handle HTTPS redirects
    
    # Storage configuration
    storage file_system {{
        root {self.dirs['data']}
    }}
}}

{config.domain} {{
    reverse_proxy {config.target} {{
        # Health checks
        health_uri /health
        health_interval 30s
        health_timeout 10s
        
        # Headers
        header_up Host {config.domain}
        header_up X-Real-IP {{remote_host}}
        header_up X-Forwarded-For {{remote_host}}
        header_up X-Forwarded-Proto {{scheme}}
    }}
    
    tls {{
        dns cloudflare {cloudflare_auth}
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
    }}"""

            # Add any additional configuration
            if config.additional_config:
                for key, value in config.additional_config.items():
                    caddy_config += f"\n    {key} {value}"
                    
            caddy_config += "\n}\n"
        
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
            config_path = Path(config_str)
            if not config_path.exists():
                raise ProxyError(f"Configuration file not found: {config_str}")
                
            if not self.binary_path.exists():
                raise ProxyError("Caddy binary not found. Please run 'caddy-cloudflare install' first.")
                
            result = subprocess.run(
                [str(self.binary_path), 'validate', '--config', str(config_path)],
                capture_output=True,
                text=True,
                check=False  # Don't raise exception on non-zero exit
            )
            
            if result.returncode != 0:
                logger.error(f"Configuration validation failed: {result.stderr}")
                return False
                
            logger.info("Configuration validation successful")
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Configuration validation failed: {str(e)}")
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
            
            # Set Cloudflare credentials based on available authentication method
            if self.config.cloudflare_zone_token and self.config.cloudflare_dns_token:
                logger.info("Using Zone and DNS tokens for Caddy authentication")
                env['CLOUDFLARE_ZONE_TOKEN'] = self.config.cloudflare_zone_token
                env['CLOUDFLARE_DNS_TOKEN'] = self.config.cloudflare_dns_token
            elif self.config.cloudflare_token:
                logger.info("Using API Token for Caddy authentication")
                env['CLOUDFLARE_API_TOKEN'] = self.config.cloudflare_token
            elif self.config.cloudflare_api_key and self.config.cloudflare_api_email:
                logger.info("Using Global API Key for Caddy authentication")
                env['CLOUDFLARE_API_KEY'] = self.config.cloudflare_api_key
                env['CLOUDFLARE_EMAIL'] = self.config.cloudflare_api_email
            
            # Start Caddy with proper logging
            command = [
                str(self.binary_path),
                'run',
                '--config', str(config_file),
                '--pidfile', str(self._pid_file)
            ]
            
            logger.debug(f"Starting Caddy with command: {' '.join(command)}")
            logger.debug(f"Environment variables: CLOUDFLARE_API_TOKEN={'Set' if 'CLOUDFLARE_API_TOKEN' in env else 'Not set'}, " +
                        f"CLOUDFLARE_DNS_TOKEN={'Set' if 'CLOUDFLARE_DNS_TOKEN' in env else 'Not set'}, " +
                        f"CLOUDFLARE_ZONE_TOKEN={'Set' if 'CLOUDFLARE_ZONE_TOKEN' in env else 'Not set'}, " +
                        f"CLOUDFLARE_API_KEY={'Set' if 'CLOUDFLARE_API_KEY' in env else 'Not set'}, " +
                        f"CLOUDFLARE_EMAIL={'Set' if 'CLOUDFLARE_EMAIL' in env else 'Not set'}")
            
            # First, try to start normally
            try:
                self._process = subprocess.Popen(
                    command,
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
                    
                    # Check if we got a permission error and need to use sudo
                    if "permission denied" in error.lower() and "bind: permission denied" in error.lower():
                        logger.info("Permission denied for port binding. Attempting to start with sudo...")
                        
                        # Use sudo to start Caddy
                        sudo_command = ["sudo"] + command
                        logger.debug(f"Starting Caddy with elevated privileges: {' '.join(sudo_command)}")
                        
                        # Create a file with the environment variables
                        env_file = Path('/tmp/caddy_env')
                        with open(env_file, 'w') as f:
                            for key, value in env.items():
                                if key.startswith('CLOUDFLARE_'):
                                    f.write(f"export {key}='{value}'\n")
                        
                        # Make the environment file readable only by current user
                        env_file.chmod(0o600)
                        
                        try:
                            # Start Caddy with sudo, preserving environment variables
                            sudo_command_str = f"source {env_file} && " + " ".join(sudo_command)
                            self._process = subprocess.Popen(
                                ["sudo", "bash", "-c", sudo_command_str],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                start_new_session=True  # Detach from parent process
                            )
                            
                            # Wait for startup
                            time.sleep(2)  # Give Caddy time to start
                            
                            # Check if started successfully with sudo
                            if self._process.poll() is not None:
                                error = self._process.stderr.read().decode('utf-8')
                                
                                # Log the full error details
                                logger.error(f"Caddy failed to start with sudo. Process exited with code {self._process.returncode}")
                                logger.error(f"Error details: {error}")
                                
                                raise ProxyError(f"Failed to start Caddy with elevated privileges: {error[:200]}")
                            
                            # Clean up environment file
                            os.unlink(env_file)
                            
                            # Save PID
                            self._save_pid()
                            
                            logger.info(f"Started Caddy server with sudo, PID {self._process.pid}")
                            return ProxyStatus(
                                running=True,
                                pid=self._process.pid,
                                config_file=Path(config_file),
                                error=None
                            )
                        except Exception as e:
                            logger.error(f"Failed to start Caddy with sudo: {str(e)}")
                            
                            # Clean up environment file
                            if env_file.exists():
                                os.unlink(env_file)
                            
                            raise ProxyError(f"Failed to start Caddy with elevated privileges: {str(e)}")
                    
                    # Log the full error details
                    logger.error(f"Caddy failed to start. Process exited with code {self._process.returncode}")
                    logger.error(f"Error details: {error}")
                    
                    # Extract meaningful error message for the user
                    error_message = "Failed to start Caddy"
                    
                    # Check for common error patterns and provide more helpful messages
                    if "dns/cloudflare" in error and "unknown directive" in error:
                        error_message = "Failed to start Caddy: The Cloudflare DNS module is not available. " \
                                       "Make sure you have the correct Caddy build with the Cloudflare DNS provider enabled."
                    elif "permission denied" in error.lower():
                        error_message = "Failed to start Caddy: Permission denied. " \
                                       "Try running with elevated privileges or check file permissions."
                    elif "address already in use" in error.lower():
                        error_message = "Failed to start Caddy: Address already in use. " \
                                       "Another service might be using port 443 or 80."
                    elif "invalid caddy environment" in error.lower():
                        error_message = "Failed to start Caddy: Invalid environment configuration. " \
                                       "Check your Cloudflare credentials."
                    elif "no oauth token provided" in error.lower() or "api token" in error.lower():
                        error_message = "Failed to start Caddy: Authentication error with Cloudflare. " \
                                       "Check that your API tokens are correct and have the required permissions."
                    elif error.strip():
                        # If we have an error but it doesn't match known patterns, include the first part
                        lines = error.strip().split('\n')
                        if lines:
                            error_message = f"Failed to start Caddy: {lines[0][:200]}"
                    
                    raise ProxyError(error_message)
                
                # Save PID
                self._save_pid()
                
                logger.info(f"Started Caddy server with PID {self._process.pid}")
                return ProxyStatus(
                    running=True,
                    pid=self._process.pid,
                    config_file=Path(config_file),
                    error=None
                )
                
            except subprocess.SubprocessError as e:
                raise ProxyError(f"Failed to execute Caddy: {str(e)}")
            
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
    
    def install(self, system_wide: bool = True) -> bool:
        """Install Caddy binary"""
        try:
            # Get system info
            from ..utils import get_system_info
            import subprocess
            import json
            import os
            os_type, arch = get_system_info()
            
            # Try to get the latest version from GitHub API
            try:
                logger.info("Checking for latest version of custom Caddy binary...")
                cmd = ["curl", "-s", "https://api.github.com/repos/tadeasf/caddy_cloudflare_cli/releases/latest"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    release_info = json.loads(result.stdout)
                    version = release_info["tag_name"].lstrip("v")
                    logger.info(f"Found latest version: {version}")
                else:
                    # Fallback to known version if API call fails
                    version = "0.10.0"
                    logger.warning(f"Could not fetch latest version, using fallback version: {version}")
            except Exception as e:
                # Fallback to known version if API call fails
                version = "0.10.0"
                logger.warning(f"Error checking latest version: {str(e)}. Using fallback version: {version}")
            
            os_type_str = "linux" if os_type == "linux" else "windows" if os_type == "windows" else "darwin"
            arch_str = "amd64" if arch == "amd64" or arch == "x86_64" else "arm64" if arch == "arm64" else arch
            
            # Use the custom binary from the project's GitHub releases
            binary_name = f"caddy-cloudflare-{os_type_str}-{arch_str}"
            url = f"https://github.com/tadeasf/caddy_cloudflare_cli/releases/download/v{version}/{binary_name}"
            
            logger.info(f"Downloading custom Caddy binary with Cloudflare DNS plugin from: {url}")
            
            # Determine installation location based on system_wide flag
            if system_wide:
                # For system-wide install, use /usr/local/bin
                target_dir = Path('/usr/local/bin')
                
                # Check if we have permission to write to system directory
                if not os.access(target_dir, os.W_OK):
                    logger.warning("No write permissions for system directory. Attempting with sudo...")
                    
                    # Download to temporary location
                    temp_path = Path('/tmp') / binary_name
                    from ..utils import download_file
                    if not download_file(url, temp_path):
                        raise ProxyError("Failed to download Caddy binary")
                    
                    # Make executable
                    temp_path.chmod(0o755)
                    
                    # Move to system location with sudo
                    target_path = target_dir / 'caddy'
                    cmd = ["sudo", "mv", str(temp_path), str(target_path)]
                    result = subprocess.run(cmd)
                    if result.returncode != 0:
                        raise ProxyError("Failed to move Caddy binary to system directory. Try running with sudo.")
                    
                    # Set permissions with sudo
                    subprocess.run(["sudo", "chmod", "755", str(target_path)])
                    
                    # Set binary path to system location
                    self.binary_path = target_path
                    logger.info(f"Installed custom Caddy binary with Cloudflare DNS plugin at {target_path}")
                    return True
                else:
                    # We have permissions, install directly
                    target_path = target_dir / 'caddy'
                    from ..utils import download_file
                    if not download_file(url, target_path):
                        raise ProxyError("Failed to download Caddy binary")
                    
                    # Make executable
                    target_path.chmod(0o755)
                    
                    # Set binary path to system location
                    self.binary_path = target_path
                    logger.info(f"Installed custom Caddy binary with Cloudflare DNS plugin at {target_path}")
                    return True
            else:
                # User installation
                # Create binary directory
                binary_dir = self.binary_path.parent
                binary_dir.mkdir(parents=True, exist_ok=True)
                
                # Download binary directly
                from ..utils import download_file
                if not download_file(url, self.binary_path):
                    raise ProxyError("Failed to download Caddy binary")
                
                # Make executable
                self.binary_path.chmod(0o755)
                
                logger.info(f"Installed custom Caddy binary with Cloudflare DNS plugin at {self.binary_path}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to install Caddy: {str(e)}")
            if self.binary_path.exists():
                self.binary_path.unlink()
            return False
    
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
