"""
ODIN Protocol Security Hardening

Provides enhanced security features including:
- Certificate pinning for critical endpoints
- Enhanced audit logging with security events
- API rate limiting with abuse detection
- Security headers and OWASP compliance
"""

import ssl
import hashlib
import base64
import os
import json
from typing import Dict, List, Optional, Set, Any, Union
from datetime import datetime, timedelta
import asyncio
import aiohttp
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import logging
from dataclasses import dataclass
from enum import Enum


class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CertificatePin:
    """Certificate pin configuration."""
    hostname: str
    pins: List[str]  # SHA256 hashes of public keys
    backup_pins: List[str]  # Backup pins for rotation
    enforce: bool = True
    report_only: bool = False


@dataclass
class SecurityEvent:
    """Security event for audit logging."""
    event_type: str
    severity: SecurityLevel
    timestamp: datetime
    source_ip: str
    user_agent: Optional[str]
    details: Dict[str, Any]
    action_taken: Optional[str] = None


class CertificatePinner:
    """Certificate pinning implementation for ODIN Protocol."""
    
    def __init__(self):
        self.pins: Dict[str, CertificatePin] = {}
        self.violation_count: Dict[str, int] = {}
        self.last_violation: Dict[str, datetime] = {}
        self._load_pins()
        
    def _load_pins(self):
        """Load certificate pins from configuration."""
        # Default pins for critical ODIN endpoints
        default_pins = {
            "api.odinprotocol.com": CertificatePin(
                hostname="api.odinprotocol.com",
                pins=[
                    # These would be real SHA256 hashes in production
                    "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=",  # Example hash
                    "Vjs8r4z+80wjNcr1YKepWQboSIRi63WsWXhIMN+eWys="   # Example hash
                ],
                backup_pins=[
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  # Backup hash
                    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="   # Backup hash
                ],
                enforce=True
            ),
            "bridge.odinprotocol.com": CertificatePin(
                hostname="bridge.odinprotocol.com",
                pins=[
                    "Y9mvm0exBk1JoQ57f9Vm28jKo5lFm/woKcVxrYxu80o=",  # Example hash
                    "k2v657xBsOVe1PQRwOsHsw3bsGT2VzIqz5K+59sNQws="   # Example hash
                ],
                backup_pins=[
                    "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=",   # Backup hash
                    "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD="    # Backup hash
                ],
                enforce=True
            )
        }
        
        # Load from environment or config file
        config_file = os.getenv("ODIN_CERT_PINS_CONFIG", "cert_pins.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    
                for hostname, config in config_data.items():
                    self.pins[hostname] = CertificatePin(
                        hostname=hostname,
                        pins=config.get("pins", []),
                        backup_pins=config.get("backup_pins", []),
                        enforce=config.get("enforce", True),
                        report_only=config.get("report_only", False)
                    )
            except Exception as e:
                print(f"Failed to load certificate pins: {e}")
                
        # Use defaults if no config loaded
        if not self.pins:
            self.pins = default_pins
            
    def _extract_public_key_hash(self, cert_der: bytes) -> str:
        """Extract SHA256 hash of public key from certificate."""
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            public_key = cert.public_key()
            
            # Get public key in DER format
            public_key_der = public_key.public_key().public_bytes(
                encoding=x509.Encoding.DER,
                format=x509.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Calculate SHA256 hash
            hash_digest = hashlib.sha256(public_key_der).digest()
            return base64.b64encode(hash_digest).decode('ascii')
            
        except Exception as e:
            print(f"Failed to extract public key hash: {e}")
            return ""
            
    def verify_certificate_chain(self, hostname: str, cert_chain: List[bytes]) -> bool:
        """Verify certificate chain against pinned certificates."""
        pin_config = self.pins.get(hostname)
        if not pin_config:
            return True  # No pinning configured for this host
            
        # Extract hashes from certificate chain
        chain_hashes = []
        for cert_der in cert_chain:
            cert_hash = self._extract_public_key_hash(cert_der)
            if cert_hash:
                chain_hashes.append(cert_hash)
                
        # Check if any hash matches pinned certificates
        all_pins = pin_config.pins + pin_config.backup_pins
        pin_match = any(cert_hash in all_pins for cert_hash in chain_hashes)
        
        if not pin_match:
            self._handle_pin_violation(hostname, chain_hashes, pin_config)
            return not pin_config.enforce  # Allow if not enforcing
            
        return True
        
    def _handle_pin_violation(self, hostname: str, chain_hashes: List[str], 
                             pin_config: CertificatePin):
        """Handle certificate pin violation."""
        self.violation_count[hostname] = self.violation_count.get(hostname, 0) + 1
        self.last_violation[hostname] = datetime.utcnow()
        
        violation_details = {
            "hostname": hostname,
            "expected_pins": pin_config.pins,
            "backup_pins": pin_config.backup_pins,
            "actual_hashes": chain_hashes,
            "violation_count": self.violation_count[hostname],
            "enforce": pin_config.enforce
        }
        
        if pin_config.enforce:
            print(f"🚨 CERTIFICATE PIN VIOLATION: {hostname}")
            print(f"Expected pins: {pin_config.pins}")
            print(f"Actual hashes: {chain_hashes}")
            
        # Log security event
        from .audit_logger import log_security_event
        asyncio.create_task(log_security_event(SecurityEvent(
            event_type="certificate_pin_violation",
            severity=SecurityLevel.CRITICAL,
            timestamp=datetime.utcnow(),
            source_ip="unknown",
            user_agent=None,
            details=violation_details,
            action_taken="connection_blocked" if pin_config.enforce else "logged_only"
        )))
        
    def add_pin(self, hostname: str, pin: str, is_backup: bool = False):
        """Add certificate pin for hostname."""
        if hostname not in self.pins:
            self.pins[hostname] = CertificatePin(
                hostname=hostname,
                pins=[],
                backup_pins=[],
                enforce=True
            )
            
        if is_backup:
            self.pins[hostname].backup_pins.append(pin)
        else:
            self.pins[hostname].pins.append(pin)
            
    def remove_pin(self, hostname: str, pin: str):
        """Remove certificate pin."""
        if hostname in self.pins:
            pin_config = self.pins[hostname]
            if pin in pin_config.pins:
                pin_config.pins.remove(pin)
            if pin in pin_config.backup_pins:
                pin_config.backup_pins.remove(pin)
                
    def get_violation_stats(self) -> Dict[str, Any]:
        """Get certificate pin violation statistics."""
        return {
            "violation_count": dict(self.violation_count),
            "last_violation": {
                hostname: timestamp.isoformat()
                for hostname, timestamp in self.last_violation.items()
            },
            "configured_hosts": list(self.pins.keys())
        }


class AuditLogger:
    """Enhanced audit logging for security events."""
    
    def __init__(self):
        self.logger = logging.getLogger("odin_security")
        self.logger.setLevel(logging.INFO)
        
        # File handler for security logs
        log_file = os.getenv("ODIN_SECURITY_LOG", "odin_security.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler for critical events
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Event counters
        self.event_counts: Dict[str, int] = {}
        self.recent_events: List[SecurityEvent] = []
        
    async def log_event(self, event: SecurityEvent):
        """Log security event with structured data."""
        # Update counters
        self.event_counts[event.event_type] = self.event_counts.get(event.event_type, 0) + 1
        
        # Keep recent events for analysis
        self.recent_events.append(event)
        if len(self.recent_events) > 1000:
            self.recent_events = self.recent_events[-500:]  # Keep last 500
            
        # Log message
        log_data = {
            "event_type": event.event_type,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "source_ip": event.source_ip,
            "user_agent": event.user_agent,
            "details": event.details,
            "action_taken": event.action_taken
        }
        
        log_message = f"Security Event: {json.dumps(log_data)}"
        
        if event.severity in [SecurityLevel.CRITICAL, SecurityLevel.HIGH]:
            self.logger.error(log_message)
        elif event.severity == SecurityLevel.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
            
        # Send to external SIEM if configured
        await self._send_to_siem(event)
        
    async def _send_to_siem(self, event: SecurityEvent):
        """Send security event to external SIEM system."""
        siem_url = os.getenv("ODIN_SIEM_URL")
        siem_token = os.getenv("ODIN_SIEM_TOKEN")
        
        if not siem_url or not siem_token:
            return
            
        try:
            payload = {
                "timestamp": event.timestamp.isoformat(),
                "source": "odin_protocol",
                "event_type": event.event_type,
                "severity": event.severity.value,
                "source_ip": event.source_ip,
                "details": event.details
            }
            
            headers = {
                "Authorization": f"Bearer {siem_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(siem_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        print(f"Failed to send event to SIEM: {response.status}")
                        
        except Exception as e:
            print(f"SIEM integration error: {e}")
            
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics for monitoring."""
        recent_events_by_type = {}
        critical_events = 0
        
        # Analyze recent events
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        for event in self.recent_events:
            if event.timestamp >= cutoff_time:
                recent_events_by_type[event.event_type] = recent_events_by_type.get(
                    event.event_type, 0
                ) + 1
                if event.severity == SecurityLevel.CRITICAL:
                    critical_events += 1
                    
        return {
            "total_events": dict(self.event_counts),
            "recent_24h": recent_events_by_type,
            "critical_events_24h": critical_events,
            "total_recent_events": len([
                e for e in self.recent_events if e.timestamp >= cutoff_time
            ])
        }


class RateLimiter:
    """Rate limiting with abuse detection."""
    
    def __init__(self):
        self.request_counts: Dict[str, List[datetime]] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.rules = {
            "default": {"requests": 100, "window": 3600},  # 100 req/hour
            "api_key": {"requests": 1000, "window": 3600},  # 1000 req/hour with API key
            "bridge_pro": {"requests": 50, "window": 3600},  # 50 req/hour for Bridge Pro
            "research": {"requests": 200, "window": 3600}    # 200 req/hour for Research
        }
        
    def is_allowed(self, client_id: str, rule_type: str = "default") -> bool:
        """Check if request is allowed under rate limits."""
        now = datetime.utcnow()
        
        # Check if IP is blocked
        if client_id in self.blocked_ips:
            if now < self.blocked_ips[client_id]:
                return False
            else:
                del self.blocked_ips[client_id]
                
        # Get rate limit rule
        rule = self.rules.get(rule_type, self.rules["default"])
        window_start = now - timedelta(seconds=rule["window"])
        
        # Initialize or clean request history
        if client_id not in self.request_counts:
            self.request_counts[client_id] = []
            
        # Remove old requests outside window
        self.request_counts[client_id] = [
            req_time for req_time in self.request_counts[client_id]
            if req_time > window_start
        ]
        
        # Check if limit exceeded
        if len(self.request_counts[client_id]) >= rule["requests"]:
            # Block IP for 1 hour if excessive requests
            if len(self.request_counts[client_id]) > rule["requests"] * 2:
                self.blocked_ips[client_id] = now + timedelta(hours=1)
                
            return False
            
        # Record this request
        self.request_counts[client_id].append(now)
        return True
        
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        now = datetime.utcnow()
        active_clients = len([
            client_id for client_id, requests in self.request_counts.items()
            if requests and requests[-1] > now - timedelta(hours=1)
        ])
        
        return {
            "active_clients": active_clients,
            "blocked_ips": len(self.blocked_ips),
            "total_tracked_clients": len(self.request_counts),
            "rules": self.rules
        }


# Global instances
_cert_pinner: Optional[CertificatePinner] = None
_audit_logger: Optional[AuditLogger] = None
_rate_limiter: Optional[RateLimiter] = None


def get_certificate_pinner() -> CertificatePinner:
    """Get global certificate pinner instance."""
    global _cert_pinner
    if not _cert_pinner:
        _cert_pinner = CertificatePinner()
    return _cert_pinner


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if not _audit_logger:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if not _rate_limiter:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def log_security_event(event: SecurityEvent):
    """Log security event."""
    logger = get_audit_logger()
    await logger.log_event(event)


def create_security_headers() -> Dict[str, str]:
    """Create security headers for HTTP responses."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }


# Health check for security systems
async def security_health_check() -> Dict[str, Any]:
    """Check security system health."""
    try:
        cert_pinner = get_certificate_pinner()
        audit_logger = get_audit_logger()
        rate_limiter = get_rate_limiter()
        
        # Get statistics
        pin_stats = cert_pinner.get_violation_stats()
        security_metrics = audit_logger.get_security_metrics()
        rate_limit_stats = rate_limiter.get_rate_limit_stats()
        
        # Determine health status
        critical_violations = pin_stats["violation_count"]
        critical_events_24h = security_metrics["critical_events_24h"]
        
        if critical_violations or critical_events_24h > 10:
            status = "degraded"
            message = f"Security issues detected: {len(critical_violations)} pin violations, {critical_events_24h} critical events"
        else:
            status = "healthy"
            message = "All security systems operational"
            
        return {
            "status": status,
            "message": message,
            "certificate_pinning": pin_stats,
            "security_metrics": security_metrics,
            "rate_limiting": rate_limit_stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Security health check failed: {e}",
            "certificate_pinning": {},
            "security_metrics": {},
            "rate_limiting": {}
        }
