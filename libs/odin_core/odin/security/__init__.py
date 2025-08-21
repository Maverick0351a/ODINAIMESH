"""
ODIN Security Module

Advanced security features for enterprise deployment.
"""

from .keystore import (
    KeyStore,
    create_keystore,
    get_keystore
)

# Security stubs for gateway compatibility
class SecurityEvent:
    pass

class SecurityLevel:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

def get_certificate_pinner():
    """Get certificate pinner (stub)."""
    return None

def get_audit_logger():
    """Get audit logger (stub)."""
    return None

def get_rate_limiter():
    """Get rate limiter (stub)."""
    return None

def create_security_headers():
    """Create security headers (stub)."""
    return {}

def log_security_event(event_type, level, message):
    """Log security event (stub)."""
    print(f"Security: {level} - {event_type}: {message}")

def security_health_check():
    """Security health check (stub)."""
    return {"status": "healthy", "security": "active"}

__all__ = [
    "KeyStore",
    "create_keystore", 
    "get_keystore",
    "get_certificate_pinner",
    "get_audit_logger", 
    "get_rate_limiter",
    "create_security_headers",
    "log_security_event",
    "SecurityEvent",
    "SecurityLevel",
    "security_health_check"
]
