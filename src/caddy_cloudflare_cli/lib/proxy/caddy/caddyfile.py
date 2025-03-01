"""
Caddyfile parser for Caddy Cloudflare CLI
"""
import logging
import re
from pathlib import Path
from string import Template

logger = logging.getLogger(__name__)

class CaddyfileParser:
    """Parser for Caddyfile"""
    
    def __init__(self, caddyfile_path: Path):
        """
        Initialize Caddyfile parser
        
        Args:
            caddyfile_path: Path to Caddyfile
        """
        self.caddyfile_path = caddyfile_path
        self.global_config = ""
        self.site_blocks = {}
        
        # Define template paths
        template_dir = Path(__file__).parent / "Caddyfile_templates"
        self.base_template_path = template_dir / "Caddyfile"
        self.site_template_path = template_dir / "Caddyfile_update"
        
        # Load the Caddyfile if it exists
        if self.caddyfile_path.exists():
            self._parse_file(self.caddyfile_path)
    
    def _parse_file(self, file_path: Path) -> None:
        """
        Parse the Caddyfile
        
        Args:
            file_path: Path to Caddyfile
        """
        try:
            content = file_path.read_text()
            self._parse_content(content)
        except Exception as e:
            logger.error(f"Failed to parse Caddyfile: {e}")
    
    def _parse_content(self, content: str) -> None:
        """
        Parse Caddyfile content
        
        Args:
            content: Caddyfile content
        """
        try:
            # Clear existing data
            self.global_config = ""
            self.site_blocks = {}
            
            # Extract global block and site blocks
            # Pattern to match properly nested braces
            pattern = re.compile(r'(\S+\s*){([^{}]*(?:{[^{}]*(?:{[^{}]*}[^{}]*)*}[^{}]*)*)}')
            
            # Find global config block (if any)
            global_match = re.search(r'^{([^{}]*(?:{[^{}]*(?:{[^{}]*}[^{}]*)*}[^{}]*)*)}', content.strip())
            if global_match:
                self.global_config = global_match.group(0)
                # Remove the global config from content
                content = content.replace(self.global_config, '', 1).strip()
            
            # Find site blocks
            site_blocks = pattern.findall(content)
            for domain, block in site_blocks:
                # Ensure domain is clean (remove curly braces if present)
                domain = domain.strip()
                # Store the entire block with curly braces
                self.site_blocks[domain] = f"{domain} {{\n{block}\n}}"
            
            logger.debug(f"Parsed {len(self.site_blocks)} site blocks")
            
        except Exception as e:
            logger.error(f"Failed to parse Caddyfile content: {e}")
    
    def generate_config(self, email: str, data_dir: str, acme_dns_auth: str) -> str:
        """
        Generate global Caddyfile configuration
        
        Args:
            email: Email for ACME certificates
            data_dir: Data directory path
            acme_dns_auth: ACME DNS authentication config
            
        Returns:
            Generated global configuration
        """
        try:
            # Load template if not already loaded
            template_content = self.base_template_path.read_text()
            
            # Substitute template variables
            template = Template(template_content)
            return template.substitute(
                email=email,
                data_dir=data_dir,
                acme_dns_auth=acme_dns_auth
            )
        except Exception as e:
            logger.error(f"Failed to generate global configuration: {e}")
            return ""
    
    def generate_site_block(self, domain: str, target: str, cloudflare_auth: str, log_path: str) -> str:
        """
        Generate Caddyfile site block
        
        Args:
            domain: Domain to proxy
            target: Target to proxy to
            cloudflare_auth: Cloudflare authentication
            log_path: Path to log file
            
        Returns:
            Generated site block
        """
        try:
            # Load template if not already loaded
            template_content = self.site_template_path.read_text()
            
            # Substitute template variables
            template = Template(template_content)
            site_block = template.substitute(
                domain=domain,
                target=target,
                cloudflare_auth=cloudflare_auth,
                log_path=log_path
            )
            
            logger.debug(f"Generated site block for domain {domain}")
            return site_block
            
        except Exception as e:
            logger.error(f"Failed to generate site block: {e}")
            return ""
    
    def create_or_update_site(self, domain: str, target: str, cloudflare_auth: str, log_path: str) -> bool:
        """
        Create or update a site block in the Caddyfile
        
        Args:
            domain: Domain to proxy
            target: Target to proxy to
            cloudflare_auth: Cloudflare authentication
            log_path: Path to log file
            
        Returns:
            True if successful
        """
        try:
            # Generate site block
            site_block = self.generate_site_block(
                domain=domain,
                target=target,
                cloudflare_auth=cloudflare_auth,
                log_path=log_path
            )
            
            if not site_block:
                logger.error(f"Failed to generate site block for {domain}")
                return False
            
            # Store the site block
            self.site_blocks[domain] = site_block
            logger.info(f"Added site block for domain: {domain}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create or update site block: {e}")
            return False
    
    def save(self, output_path: str) -> bool:
        """
        Save the Caddyfile
        
        Args:
            output_path: Path to save the Caddyfile
            
        Returns:
            True if successful
        """
        try:
            # Start with the global config
            output = self.global_config
            
            # Ensure the global config ends with a newline
            if output and not output.endswith('\n'):
                output += '\n\n'
            elif not output:
                # If no global config, start with an empty file
                output = ''
            
            # Add site blocks
            for _, block in self.site_blocks.items():
                output += f"\n{block}\n"
            
            # Write to file
            Path(output_path).write_text(output)
            logger.info(f"Caddyfile saved to {output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save Caddyfile: {e}")
            return False
