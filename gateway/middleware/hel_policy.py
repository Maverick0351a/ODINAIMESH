"""
Research Engine HEL (HTTP Egress Limitation) policies.

Enforces security guardrails for the multi-tenant research API.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel
import ipaddress
import re


class HELPolicy(BaseModel):
    """HTTP Egress Limitation policy configuration."""
    
    max_payload_size: int = 10 * 1024 * 1024  # 10MB
    required_headers: List[str] = ["x-odin-agent"]
    blocked_domains: List[str] = [
        "localhost", "127.0.0.1", "0.0.0.0", 
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "metadata.google.internal", "169.254.169.254"
    ]
    allowed_realms: List[str] = ["business"]  # Free tier restriction
    header_redaction: List[str] = [
        "authorization", "x-api-key", "x-odin-byok-token",
        "cookie", "set-cookie", "x-auth-token"
    ]
    cors_origins: List[str] = ["https://odin.dev", "https://docs.odin.dev"]


class HELEnforcer:
    """Enforces HEL policies for research engine requests."""
    
    def __init__(self, policy: HELPolicy):
        self.policy = policy
    
    def validate_request(self, headers: Dict[str, str], 
                        body_size: int, realm: str) -> Optional[str]:
        """
        Validate request against HEL policy.
        Returns error message if violated, None if valid.
        """
        
        # Check payload size
        if body_size > self.policy.max_payload_size:
            return f"Payload exceeds limit: {body_size} > {self.policy.max_payload_size}"
        
        # Check required headers
        for header in self.policy.required_headers:
            if header.lower() not in [h.lower() for h in headers.keys()]:
                return f"Missing required header: {header}"
        
        # Check realm allowlist
        if realm not in self.policy.allowed_realms:
            return f"Realm not allowed: {realm}. Allowed: {self.policy.allowed_realms}"
        
        return None
    
    def validate_egress_url(self, url: str) -> Optional[str]:
        """
        Validate outbound URL against SSRF protection.
        Returns error message if blocked, None if allowed.
        """
        
        # Extract domain
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.hostname
            
            if not domain:
                return "Invalid URL: no hostname"
            
        except Exception as e:
            return f"Invalid URL format: {str(e)}"
        
        # Check blocked domains
        for blocked in self.policy.blocked_domains:
            if self._is_blocked_domain(domain, blocked):
                return f"Domain blocked by HEL policy: {domain}"
        
        return None
    
    def _is_blocked_domain(self, domain: str, blocked_pattern: str) -> bool:
        """Check if domain matches blocked pattern."""
        
        # Exact match
        if domain == blocked_pattern:
            return True
        
        # CIDR range check
        if "/" in blocked_pattern:
            try:
                network = ipaddress.ip_network(blocked_pattern, strict=False)
                ip = ipaddress.ip_address(domain)
                return ip in network
            except ValueError:
                pass
        
        # Wildcard match
        if "*" in blocked_pattern:
            pattern = blocked_pattern.replace("*", ".*")
            return bool(re.match(f"^{pattern}$", domain))
        
        return False
    
    def redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Redact sensitive headers from logs/receipts."""
        
        redacted = {}
        for key, value in headers.items():
            if key.lower() in [h.lower() for h in self.policy.header_redaction]:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        
        return redacted
    
    def validate_cors_origin(self, origin: str) -> bool:
        """Validate CORS origin against allowlist."""
        
        if not origin:
            return False
        
        return origin in self.policy.cors_origins


# Default HEL policy for research engine
DEFAULT_RESEARCH_HEL_POLICY = HELPolicy(
    max_payload_size=10 * 1024 * 1024,  # 10MB
    required_headers=["x-odin-agent", "x-odin-project-id"],
    blocked_domains=[
        # Private networks (RFC 1918)
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        # Loopback
        "127.0.0.0/8", "::1",
        # Link-local
        "169.254.0.0/16", "fe80::/10",
        # Cloud metadata
        "metadata.google.internal", "metadata.goog",
        "169.254.169.254", "fd00:ec2::254",
        # Common internal domains
        "localhost", "*.local", "*.internal"
    ],
    allowed_realms=["business"],  # Free tier
    header_redaction=[
        "authorization", "x-api-key", "x-odin-byok-token",
        "cookie", "set-cookie", "x-auth-token", "x-forwarded-for"
    ],
    cors_origins=[
        "https://odin.dev", 
        "https://docs.odin.dev",
        "http://localhost:3000",  # Development
        "http://localhost:5173"   # Vite dev server
    ]
)


def create_hel_enforcer() -> HELEnforcer:
    """Create HEL enforcer with default research policy."""
    return HELEnforcer(DEFAULT_RESEARCH_HEL_POLICY)
