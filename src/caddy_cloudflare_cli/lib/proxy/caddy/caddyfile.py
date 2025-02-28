"""
Caddyfile parsing and manipulation for Caddy Proxy
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from string import Template
import os

logger = logging.getLogger(__name__)

class CaddyfileParser:
    """Handles parsing and manipulation of Caddyfile"""
    
    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        """Initialize parser with optional file path"""
        self.file_path = Path(file_path) if file_path else None
        self.global_options = []
        self.site_blocks = {}
        self._current_content = ""
        self.template_dir = Path(__file__).parent / "Caddyfile_templates"
        self.logger = logger
        
        if self.file_path and self.file_path.exists():
            self.load()
    
    def load(self, file_path: Optional[Union[str, Path]] = None) -> bool:
        """Load Caddyfile from disk"""
        if file_path:
            self.file_path = Path(file_path)
        
        if not self.file_path or not self.file_path.exists():
            logger.warning(f"Caddyfile not found at {self.file_path}")
            return False
        
        try:
            self._current_content = self.file_path.read_text()
            self._parse_content(self._current_content)
            return True
        except Exception as e:
            logger.error(f"Failed to load Caddyfile: {str(e)}")
            return False
    
    def _parse_content(self, content: str) -> None:
        """
        Parse Caddyfile content and extract global options and site blocks
        
        Args:
            content: Caddyfile content to parse
        """
        # Reset parser state
        self.global_options = []
        self.site_blocks = {}
        
        lines = content.strip().split('\n')
        
        current_block = None
        current_domain = None
        current_content = []
        in_global_block = False
        brace_counter = 0
        
        # Process line by line
        for line_idx, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Skip empty lines
            if not stripped_line or stripped_line.startswith("#"):
                continue
                
            # Handle opening braces
            if stripped_line == '{':
                brace_counter += 1
                if current_block is None and not in_global_block:
                    in_global_block = True
                continue
                
            # Handle closing braces
            if stripped_line == '}':
                brace_counter -= 1
                if brace_counter == 0 and in_global_block:
                    in_global_block = False
                    continue
                if brace_counter == 0 and current_block is not None:
                    # End of a site block
                    self.site_blocks[current_domain] = current_content
                    current_block = None
                    current_domain = None
                    current_content = []
                    continue
                    
            # Add to current block
            if in_global_block:
                self.global_options.append(stripped_line)
            elif current_block is not None:
                current_content.append(stripped_line)
            elif '{' in stripped_line and not stripped_line.startswith('#'):
                # Start of a site block
                parts = stripped_line.split('{', 1)
                current_domain = parts[0].strip()
                current_block = 'site'
                brace_counter += 1
                
                # If there's content after the opening brace, process it
                if len(parts) > 1 and parts[1].strip():
                    remainder = parts[1].strip()
                    if remainder.endswith('}'):
                        remainder = remainder[:-1].strip()
                        brace_counter -= 1  # Adjust the counter if we found a closing brace
                    if remainder:
                        current_content.append(remainder)
                    
                    # If we've reached the end of the block already
                    if brace_counter == 0:
                        self.site_blocks[current_domain] = current_content
                        current_block = None
                        current_domain = None
                        current_content = []
            else:
                # Add to global section outside of any braces
                self.global_options.append(stripped_line)
        
        # Handle any unclosed blocks at the end of file
        if current_block is not None and current_domain is not None and current_content:
            logger.warning(f"Found unclosed site block for {current_domain} at end of file")
            self.site_blocks[current_domain] = current_content
    
    def has_site(self, domain: str) -> bool:
        """Check if site block exists for domain"""
        return domain in self.site_blocks
    
    def add_site(self, domain: str, config_content: Union[str, List[str]]) -> bool:
        """Add a new site block"""
        if isinstance(config_content, str):
            config_content = config_content.strip().split('\n')
            
        # Clean up the content to ensure proper formatting
        cleaned_content = []
        for line in config_content:
            line = line.rstrip()
            if line and not line.isspace():
                # Remove braces that might be part of the line content
                if line == '{' or line == '}':
                    continue  # Skip standalone braces
                if line.startswith('{') and len(line) > 1:
                    line = line[1:].lstrip()
                if line.endswith('}') and len(line) > 1:
                    line = line[:-1].rstrip()
                cleaned_content.append(line)
        
        self.site_blocks[domain] = cleaned_content
        return True
    
    def update_site(self, domain: str, config_content: Union[str, List[str]]) -> bool:
        """Update existing site block"""
        if domain not in self.site_blocks:
            logger.warning(f"Site {domain} not found in Caddyfile")
            return False
            
        if isinstance(config_content, str):
            config_content = config_content.strip().split('\n')
            
        # Clean up the content to ensure proper formatting
        cleaned_content = []
        for line in config_content:
            line = line.rstrip()
            if line and not line.isspace():
                # Remove braces that might be part of the line content
                if line == '{' or line == '}':
                    continue  # Skip standalone braces
                if line.startswith('{') and len(line) > 1:
                    line = line[1:].lstrip()
                if line.endswith('}') and len(line) > 1:
                    line = line[:-1].rstrip()
                cleaned_content.append(line)
        
        self.site_blocks[domain] = cleaned_content
        return True
    
    def remove_site(self, domain: str) -> bool:
        """Remove a site block"""
        if domain not in self.site_blocks:
            logger.warning(f"Site {domain} not found in Caddyfile")
            return False
            
        del self.site_blocks[domain]
        return True
    
    def update_global_options(self, options: Union[str, List[str]]) -> None:
        """Update global options"""
        if isinstance(options, str):
            options = options.strip().split('\n')
            
        # Strip any existing braces from the options
        cleaned_options = []
        for line in options:
            line = line.strip()
            if line.startswith('{'):
                line = line[1:].strip()
            if line.endswith('}'):
                line = line[:-1].strip()
            if line:
                cleaned_options.append(line)
        
        self.global_options = cleaned_options
    
    def to_string(self) -> str:
        """Convert parsed Caddyfile back to string"""
        output = []
        
        # Add global options
        if self.global_options:
            output.append("{")
            for line in self.global_options:
                output.append(f"    {line}")
            output.append("}")
            output.append("")  # Empty line after global block
        
        # Add site blocks
        for domain, content in self.site_blocks.items():
            output.append(f"{domain} {{")
            for line in content:
                output.append(f"    {line}")
            output.append("}")
            output.append("")  # Empty line between site blocks
        
        return "\n".join(output)
    
    def save(self) -> bool:
        """
        Save the Caddyfile to disk
        
        This ensures that all existing site blocks are preserved and only
        updated blocks are modified.
        
        Returns:
            True if successful
        """
        try:
            # Ensure parent directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build Caddyfile content
            content = []
            
            # Add global options block if any
            if self.global_options:
                content.append("{")
                for line in self.global_options:
                    content.append(f"\t{line}")
                content.append("}")
                content.append("")  # Add empty line after global options
            
            # Add site blocks
            for domain, lines in self.site_blocks.items():
                content.append(f"{domain} {{")
                for line in lines:
                    content.append(f"\t{line}")
                content.append("}")
                content.append("")  # Add empty line after each site block
            
            # Write to file
            with open(self.file_path, 'w') as f:
                f.write("\n".join(content))
            
            logger.info(f"Saved Caddyfile to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save Caddyfile: {str(e)}")
            return False
            
    def _load_template(self, template_name: str) -> str:
        """Load a template file from the templates directory"""
        template_path = self.template_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        return template_path.read_text()
        
    def generate_from_template(self, template_values: Dict[str, Any], 
                              template_name: str = "Caddyfile") -> str:
        """
        Generate a Caddyfile from a template
        
        Args:
            template_values: Dictionary of values to substitute in the template
            template_name: Name of the template file to use
            
        Returns:
            Generated Caddyfile content
        """
        template_content = self._load_template(template_name)
        template = Template(template_content)
        return template.safe_substitute(template_values)
        
    def generate_site_block_from_template(self, domain, template, target, cloudflare_auth, log_path, additional_config=""):
        """
        Generate a site block from a template.

        Args:
            domain (str): The domain to generate the site block for.
            template (str): The template to use.
            target (str): The target to use.
            cloudflare_auth (str): The Cloudflare authentication to use.
            log_path (str): The log path to use.
            additional_config (str, optional): Additional configuration to add to the site block. Defaults to "".

        Returns:
            str: The generated site block.
        """
        try:
            # Ensure all the parameters are strings and strip any whitespace
            domain = str(domain).strip() if domain is not None else ""
            target = str(target).strip() if target is not None else ""
            cloudflare_auth = str(cloudflare_auth).strip() if cloudflare_auth is not None else ""
            log_path = str(log_path).strip() if log_path is not None else ""
            additional_config = str(additional_config).strip() if additional_config is not None else ""
            
            # Create a substitution dictionary
            # We need to handle Caddy's placeholders ({remote_host}, {scheme}) specially
            # Use string Template with a different pattern than Caddy's curly braces
            modified_template = template.replace("{remote_host}", "<<remote_host>>")
            modified_template = modified_template.replace("{scheme}", "<<scheme>>")
            
            # Create Template object with the modified template
            template_obj = Template(modified_template)
            
            # Prepare substitutions
            substitutions = {
                "domain": domain,
                "target": target,
                "cloudflare_auth": cloudflare_auth,
                "log_path": log_path,
            }
            
            # Perform substitution
            result = template_obj.safe_substitute(substitutions)
            
            # Restore Caddy's placeholders
            result = result.replace("<<remote_host>>", "{remote_host}")
            result = result.replace("<<scheme>>", "{scheme}")
            
            # Add additional configuration if provided
            if additional_config:
                # Find the last closing brace
                last_brace_index = result.rfind('}')
                if last_brace_index != -1:
                    # Insert additional config before the last closing brace
                    result = result[:last_brace_index] + "\n    " + additional_config + "\n" + result[last_brace_index:]
            
            # Count braces to ensure proper closure
            open_braces = result.count('{')
            close_braces = result.count('}')
            
            if open_braces > close_braces:
                # Add missing closing braces
                missing_braces = open_braces - close_braces
                self.logger.warning(f"Adding {missing_braces} missing closing braces to template")
                result += '\n' + '}' * missing_braces
            elif close_braces > open_braces:
                # Remove extra closing braces
                self.logger.warning(f"Template has {close_braces - open_braces} extra closing braces")
                # We don't modify this case as it's trickier to fix without causing other issues
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to generate site block from template: {e}")
            return None
        
    def generate_global_options_from_template(self, 
                                             email: str, 
                                             data_dir: str,
                                             acme_dns_config: str) -> str:
        """
        Generate global options using the global template
        
        Args:
            email: Email address for ACME certificates
            data_dir: Data directory for storage
            acme_dns_config: ACME DNS configuration for Cloudflare
            
        Returns:
            Generated global options configuration
        """
        # Ensure data_dir is a string for template substitution
        data_dir_str = str(data_dir) if data_dir is not None else ""
        
        template_values = {
            "email": email if email is not None else "",
            "data_dir": data_dir_str,
            "acme_dns_config": acme_dns_config if acme_dns_config is not None else ""
        }
        
        return self.generate_from_template(template_values, "Caddyfile")
        
    def create_or_update_site(self, domain, template, target, cloudflare_auth, log_path, additional_config=""):
        """
        Create or update a site in the Caddyfile.

        Args:
            domain (str): The domain to create or update.
            template (str): The template to use.
            target (str): The target to use.
            cloudflare_auth (str): The Cloudflare authentication to use.
            log_path (str): The log path to use.
            additional_config (str or dict, optional): Additional configuration to add to the site block. Defaults to "".

        Returns:
            bool: True if the site was created or updated, False otherwise.
        """
        try:
            # Convert additional_config dict to string if needed
            if isinstance(additional_config, dict):
                additional_config_str = ""
                for key, value in additional_config.items():
                    additional_config_str += f"{key} {value}\n"
            else:
                additional_config_str = str(additional_config) if additional_config else ""
            
            site_block = self.generate_site_block_from_template(
                domain, template, target, cloudflare_auth, log_path, additional_config_str
            )
            
            if site_block is None:
                return False
            
            # Parse the content to ensure it's valid
            content_lines = site_block.strip().split('\n')
            
            # Extract site content (everything between the opening and closing braces)
            site_content = ''
            in_site_block = False
            brace_counter = 0
            
            for line in content_lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith(domain):
                    in_site_block = True
                    continue
                
                if in_site_block:
                    # Count braces to detect end of block
                    brace_counter += line.count('{')
                    brace_counter -= line.count('}')
                    
                    # Add line to site content
                    site_content += line + '\n'
                    
                    # Check if we've reached the end of the site block
                    if brace_counter == 0:
                        break
            
            # Remove trailing newline and closing brace if present
            site_content = site_content.strip()
            if site_content.endswith('}'):
                site_content = site_content[:-1].strip()
            
            # Add or update the site
            if domain in self.site_blocks:
                self.logger.info(f"Updating site block for domain: {domain}")
                self.update_site(domain, site_content)
            else:
                self.logger.info(f"Adding site block for domain: {domain}")
                self.add_site(domain, site_content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create or update site: {e}")
            return False
    
    def initialize_with_global_options(self, email, data_dir, acme_dns_auth):
        """
        Initialize the Caddyfile with global options.

        Args:
            email (str): The email to use for ACME.
            data_dir (str or Path): The data directory to use.
            acme_dns_auth (str): The ACME DNS authentication configuration.

        Returns:
            bool: True if the global options were initialized, False otherwise.
        """
        try:
            self.logger.debug(f"Initializing with global options: email={email}, data_dir={data_dir}, type(data_dir)={type(data_dir)}")
            
            # Ensure data_dir is valid
            if data_dir is None:
                data_dir = Path('~/.caddy-cloudflare/data').expanduser()
                self.logger.debug(f"Using default data_dir: {data_dir}")
            
            # Convert to Path if it's a string
            if isinstance(data_dir, str):
                old_data_dir = data_dir
                data_dir = Path(data_dir)
                if '~' in old_data_dir:
                    data_dir = data_dir.expanduser()
                self.logger.debug(f"Converted string to Path: {data_dir}")
            
            # Ensure it's a Path object at this point
            if not isinstance(data_dir, Path):
                self.logger.warning(f"data_dir is not a Path object: {data_dir}, type: {type(data_dir)}")
                data_dir = Path(str(data_dir))
                self.logger.debug(f"Converted to Path object: {data_dir}")
            
            self.logger.debug(f"Final data_dir value: {data_dir}, type: {type(data_dir)}")
            
            # Build global options
            global_options = []
            global_options.append("admin off  # Disable admin API for security")
            global_options.append("auto_https disable_redirects  # Let Cloudflare handle HTTPS redirects")
            
            if email:
                global_options.append(f"email {email}")
            
            if acme_dns_auth and acme_dns_auth.strip():
                global_options.append(acme_dns_auth.strip())
            
            # Add storage configuration
            try:
                storage_path = data_dir / "storage"
                self.logger.debug(f"Storage path: {storage_path}")
                global_options.append(f"storage file_system {{")
                global_options.append(f"    root {storage_path}")
                global_options.append(f"}}")
            except Exception as e:
                self.logger.error(f"Error creating storage path: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            # Set the global options
            self.global_options = global_options
            self.logger.debug(f"Global options set: {global_options}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize with global options: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
