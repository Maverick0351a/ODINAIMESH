"""
SIEM/SOAR Integration for ODIN Protocol

Push high-severity HEL denials/drift alerts to PagerDuty/ServiceNow with trace links.
Provides real-time security event streaming to enterprise security platforms.
"""

from __future__ import annotations

import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    httpx = None
    HAS_HTTPX = False

_log = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels for SIEM integration"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertCategory(Enum):
    """Security alert categories"""
    POLICY_VIOLATION = "policy_violation"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DATA_EXFILTRATION = "data_exfiltration"
    SYSTEM_COMPROMISE = "system_compromise"

@dataclass
class SecurityAlert:
    """
    Security alert for SIEM/SOAR integration.
    
    Represents a security event that should be escalated to external systems.
    """
    severity: AlertSeverity
    category: AlertCategory
    event_type: str  # Specific event type (hel_denial, unauthorized_access, etc.)
    tenant_id: str
    trace_id: Optional[str]
    timestamp: str
    title: str
    description: str
    metadata: Dict[str, Any]
    
    # Request context
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    
    # ODIN-specific context
    realm_id: Optional[str] = None
    agent_id: Optional[str] = None
    proof_kid: Optional[str] = None
    
    def to_splunk_hec_event(self) -> Dict[str, Any]:
        """Format alert for Splunk HTTP Event Collector (HEC)"""
        return {
            "time": self.timestamp,
            "source": "odin-gateway",
            "sourcetype": "odin:security:alert",
            "index": os.getenv("SPLUNK_SECURITY_INDEX", "security"),
            "host": os.getenv("HOSTNAME", "odin-gateway"),
            "event": {
                **asdict(self),
                "severity": self.severity.value,
                "category": self.category.value,
                "odin_alert": True,
                "odin_version": "0.9.0-beta",
                "environment": os.getenv("ODIN_ENVIRONMENT", "production")
            }
        }
    
    def to_pagerduty_v2_event(self) -> Dict[str, Any]:
        """Format alert for PagerDuty Events API v2"""
        # Map ODIN severity to PagerDuty severity
        pd_severity_map = {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.HIGH: "error", 
            AlertSeverity.MEDIUM: "warning",
            AlertSeverity.LOW: "info",
            AlertSeverity.INFO: "info"
        }
        
        return {
            "routing_key": os.getenv("PAGERDUTY_ROUTING_KEY"),
            "event_action": "trigger",
            "dedup_key": f"odin_{self.tenant_id}_{self.event_type}_{hash(self.trace_id or self.timestamp)}",
            "payload": {
                "summary": f"ODIN Security Alert: {self.title}",
                "source": f"odin-gateway-{self.tenant_id}",
                "severity": pd_severity_map.get(self.severity, "info"),
                "component": "odin-protocol",
                "group": "security",
                "class": self.category.value,
                "custom_details": {
                    **self.metadata,
                    "tenant_id": self.tenant_id,
                    "event_type": self.event_type,
                    "realm_id": self.realm_id,
                    "agent_id": self.agent_id,
                    "proof_kid": self.proof_kid,
                    "source_ip": self.source_ip,
                    "request_path": self.request_path,
                    "odin_version": "0.9.0-beta"
                }
            },
            "links": self._build_pagerduty_links()
        }
    
    def to_servicenow_incident(self) -> Dict[str, Any]:
        """Format alert for ServiceNow Incident Creation API"""
        # Map ODIN severity to ServiceNow priority
        sn_priority_map = {
            AlertSeverity.CRITICAL: "1",  # Critical
            AlertSeverity.HIGH: "2",      # High
            AlertSeverity.MEDIUM: "3",    # Moderate
            AlertSeverity.LOW: "4",       # Low
            AlertSeverity.INFO: "5"       # Planning
        }
        
        return {
            "short_description": f"ODIN Security Alert: {self.title}",
            "description": self._build_servicenow_description(),
            "category": "Security",
            "subcategory": self.category.value.replace("_", " ").title(),
            "priority": sn_priority_map.get(self.severity, "3"),
            "impact": "2" if self.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH] else "3",
            "urgency": "1" if self.severity == AlertSeverity.CRITICAL else "2",
            "caller_id": "odin-protocol",
            "assignment_group": os.getenv("SERVICENOW_ASSIGNMENT_GROUP", "Security Team"),
            "business_service": "ODIN Protocol",
            "cmdb_ci": f"odin-gateway-{self.tenant_id}",
            "work_notes": json.dumps({
                "odin_metadata": self.metadata,
                "trace_id": self.trace_id,
                "tenant_id": self.tenant_id,
                "event_type": self.event_type
            }, indent=2)
        }
    
    def _build_pagerduty_links(self) -> List[Dict[str, str]]:
        """Build links for PagerDuty alert"""
        links = []
        
        # Trace link
        if self.trace_id:
            trace_url = os.getenv("ODIN_TRACE_URL", "https://your-tracing-system.com")
            links.append({
                "href": f"{trace_url}/trace/{self.trace_id}",
                "text": "View Full Trace"
            })
        
        # ODIN Gateway logs
        gateway_logs_url = os.getenv("ODIN_LOGS_URL", "https://your-logs-system.com")
        if gateway_logs_url:
            links.append({
                "href": f"{gateway_logs_url}/logs?q=tenant_id:{self.tenant_id}+timestamp:{self.timestamp}",
                "text": "View Gateway Logs"
            })
        
        # Tenant dashboard
        tenant_dashboard_url = os.getenv("ODIN_TENANT_DASHBOARD_URL")
        if tenant_dashboard_url:
            links.append({
                "href": f"{tenant_dashboard_url}/tenant/{self.tenant_id}",
                "text": "Tenant Dashboard"
            })
        
        return links
    
    def _build_servicenow_description(self) -> str:
        """Build detailed description for ServiceNow incident"""
        description_parts = [
            f"Security Alert: {self.description}",
            "",
            "== Alert Details ==",
            f"Severity: {self.severity.value.upper()}",
            f"Category: {self.category.value.replace('_', ' ').title()}",
            f"Event Type: {self.event_type}",
            f"Timestamp: {self.timestamp}",
            "",
            "== ODIN Context ==",
            f"Tenant ID: {self.tenant_id}",
            f"Realm ID: {self.realm_id or 'N/A'}",
            f"Agent ID: {self.agent_id or 'N/A'}",
            f"Proof Kid: {self.proof_kid or 'N/A'}",
            "",
            "== Request Context ==",
            f"Source IP: {self.source_ip or 'N/A'}",
            f"Request Path: {self.request_path or 'N/A'}",
            f"Request Method: {self.request_method or 'N/A'}",
            f"User Agent: {self.user_agent or 'N/A'}",
            "",
            "== Trace Information ==",
            f"Trace ID: {self.trace_id or 'N/A'}"
        ]
        
        if self.metadata:
            description_parts.extend([
                "",
                "== Additional Metadata ==",
                json.dumps(self.metadata, indent=2)
            ])
        
        return "\n".join(description_parts)

class SIEMIntegration:
    """
    SIEM/SOAR integration service for ODIN Protocol.
    
    Dispatches security alerts to multiple external systems simultaneously.
    """
    
    def __init__(self):
        self.enabled = os.getenv("ODIN_SIEM_ENABLED", "0") == "1"
        self.webhooks = self._load_webhook_config()
        self.alert_thresholds = self._load_alert_thresholds()
        self.rate_limiter = AlertRateLimiter()
        
    def _load_webhook_config(self) -> Dict[str, Dict[str, Any]]:
        """Load webhook configurations from environment"""
        webhooks = {}
        
        # Splunk HEC configuration
        if os.getenv("SPLUNK_HEC_URL") and os.getenv("SPLUNK_HEC_TOKEN"):
            webhooks["splunk"] = {
                "url": os.getenv("SPLUNK_HEC_URL"),
                "headers": {
                    "Authorization": f"Splunk {os.getenv('SPLUNK_HEC_TOKEN')}",
                    "Content-Type": "application/json"
                },
                "timeout": int(os.getenv("SPLUNK_TIMEOUT", "30"))
            }
        
        # PagerDuty configuration
        if os.getenv("PAGERDUTY_ROUTING_KEY"):
            webhooks["pagerduty"] = {
                "url": "https://events.pagerduty.com/v2/enqueue",
                "headers": {"Content-Type": "application/json"},
                "timeout": int(os.getenv("PAGERDUTY_TIMEOUT", "30"))
            }
        
        # ServiceNow configuration
        if all([os.getenv("SERVICENOW_INSTANCE"), os.getenv("SERVICENOW_USERNAME"), os.getenv("SERVICENOW_PASSWORD")]):
            webhooks["servicenow"] = {
                "url": f"https://{os.getenv('SERVICENOW_INSTANCE')}.service-now.com/api/now/table/incident",
                "headers": {"Content-Type": "application/json"},
                "auth": (os.getenv("SERVICENOW_USERNAME"), os.getenv("SERVICENOW_PASSWORD")),
                "timeout": int(os.getenv("SERVICENOW_TIMEOUT", "30"))
            }
        
        # Custom webhook configuration
        if os.getenv("CUSTOM_SIEM_WEBHOOK_URL"):
            webhooks["custom"] = {
                "url": os.getenv("CUSTOM_SIEM_WEBHOOK_URL"),
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": os.getenv("CUSTOM_SIEM_AUTH_HEADER", "")
                },
                "timeout": int(os.getenv("CUSTOM_SIEM_TIMEOUT", "30"))
            }
        
        return webhooks
    
    def _load_alert_thresholds(self) -> Dict[AlertSeverity, bool]:
        """Load alert severity thresholds"""
        return {
            AlertSeverity.CRITICAL: True,  # Always send critical alerts
            AlertSeverity.HIGH: os.getenv("SIEM_ALERT_HIGH", "1") == "1",
            AlertSeverity.MEDIUM: os.getenv("SIEM_ALERT_MEDIUM", "0") == "1",
            AlertSeverity.LOW: os.getenv("SIEM_ALERT_LOW", "0") == "1",
            AlertSeverity.INFO: os.getenv("SIEM_ALERT_INFO", "0") == "1"
        }
    
    async def emit_security_alert(self, alert: SecurityAlert) -> Dict[str, Any]:
        """
        Emit a security alert to all configured SIEM/SOAR systems.
        
        Returns a summary of dispatch results.
        """
        if not self.enabled:
            return {"status": "disabled", "dispatched": []}
        
        # Check severity threshold
        if not self.alert_thresholds.get(alert.severity, False):
            return {"status": "filtered", "reason": f"severity {alert.severity.value} below threshold"}
        
        # Check rate limiting
        if not self.rate_limiter.should_send_alert(alert):
            return {"status": "rate_limited", "reason": "similar alert sent recently"}
        
        # Dispatch to all configured systems
        dispatch_tasks = []
        
        if "splunk" in self.webhooks:
            dispatch_tasks.append(self._send_to_splunk(alert))
        
        if "pagerduty" in self.webhooks:
            dispatch_tasks.append(self._send_to_pagerduty(alert))
        
        if "servicenow" in self.webhooks:
            dispatch_tasks.append(self._send_to_servicenow(alert))
        
        if "custom" in self.webhooks:
            dispatch_tasks.append(self._send_to_custom_webhook(alert))
        
        # Execute all dispatches concurrently
        results = []
        if dispatch_tasks:
            results = await asyncio.gather(*dispatch_tasks, return_exceptions=True)
        
        # Process results
        dispatched = []
        errors = []
        
        webhook_names = [name for name in ["splunk", "pagerduty", "servicenow", "custom"] if name in self.webhooks]
        
        for i, result in enumerate(results):
            webhook_name = webhook_names[i] if i < len(webhook_names) else f"webhook_{i}"
            
            if isinstance(result, Exception):
                errors.append({"webhook": webhook_name, "error": str(result)})
            else:
                dispatched.append({"webhook": webhook_name, "result": result})
        
        return {
            "status": "dispatched",
            "dispatched": dispatched,
            "errors": errors,
            "alert_id": f"{alert.tenant_id}_{alert.event_type}_{alert.timestamp}"
        }
    
    async def _send_to_splunk(self, alert: SecurityAlert) -> Dict[str, Any]:
        """Send alert to Splunk HEC"""
        if not HAS_HTTPX:
            raise RuntimeError("httpx not available for webhook dispatch")
        
        config = self.webhooks["splunk"]
        event_data = alert.to_splunk_hec_event()
        
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                config["url"],
                headers=config["headers"],
                json=event_data
            )
            response.raise_for_status()
            
            return {
                "status_code": response.status_code,
                "response": response.json() if response.content else {}
            }
    
    async def _send_to_pagerduty(self, alert: SecurityAlert) -> Dict[str, Any]:
        """Send alert to PagerDuty"""
        if not HAS_HTTPX:
            raise RuntimeError("httpx not available for webhook dispatch")
        
        config = self.webhooks["pagerduty"]
        event_data = alert.to_pagerduty_v2_event()
        
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                config["url"],
                headers=config["headers"],
                json=event_data
            )
            response.raise_for_status()
            
            return {
                "status_code": response.status_code,
                "response": response.json() if response.content else {},
                "dedup_key": event_data.get("dedup_key")
            }
    
    async def _send_to_servicenow(self, alert: SecurityAlert) -> Dict[str, Any]:
        """Send alert to ServiceNow"""
        if not HAS_HTTPX:
            raise RuntimeError("httpx not available for webhook dispatch")
        
        config = self.webhooks["servicenow"]
        incident_data = alert.to_servicenow_incident()
        
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                config["url"],
                headers=config["headers"],
                auth=config["auth"],
                json=incident_data
            )
            response.raise_for_status()
            
            return {
                "status_code": response.status_code,
                "response": response.json() if response.content else {}
            }
    
    async def _send_to_custom_webhook(self, alert: SecurityAlert) -> Dict[str, Any]:
        """Send alert to custom webhook"""
        if not HAS_HTTPX:
            raise RuntimeError("httpx not available for webhook dispatch")
        
        config = self.webhooks["custom"]
        
        # Use Splunk format as default for custom webhooks
        event_data = alert.to_splunk_hec_event()
        
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                config["url"],
                headers=config["headers"],
                json=event_data
            )
            response.raise_for_status()
            
            return {
                "status_code": response.status_code,
                "response": response.json() if response.content else {}
            }

class AlertRateLimiter:
    """Rate limiter to prevent alert spam"""
    
    def __init__(self):
        self.recent_alerts: Dict[str, float] = {}
        self.rate_limit_window = int(os.getenv("SIEM_RATE_LIMIT_WINDOW", "300"))  # 5 minutes
    
    def should_send_alert(self, alert: SecurityAlert) -> bool:
        """Check if alert should be sent based on recent similar alerts"""
        # Create a key for similar alerts
        alert_key = f"{alert.tenant_id}_{alert.event_type}_{alert.category.value}"
        
        current_time = time.time()
        
        # Check if we've sent a similar alert recently
        if alert_key in self.recent_alerts:
            time_since_last = current_time - self.recent_alerts[alert_key]
            if time_since_last < self.rate_limit_window:
                return False
        
        # Record this alert
        self.recent_alerts[alert_key] = current_time
        
        # Clean up old entries
        self._cleanup_old_alerts(current_time)
        
        return True
    
    def _cleanup_old_alerts(self, current_time: float):
        """Remove old alert entries to prevent memory growth"""
        cutoff_time = current_time - self.rate_limit_window
        self.recent_alerts = {
            k: v for k, v in self.recent_alerts.items() 
            if v > cutoff_time
        }

# Global SIEM integration instance
_global_siem_integration: Optional[SIEMIntegration] = None

def get_siem_integration() -> SIEMIntegration:
    """Get or create the global SIEM integration instance"""
    global _global_siem_integration
    if _global_siem_integration is None:
        _global_siem_integration = SIEMIntegration()
    return _global_siem_integration

async def emit_policy_violation_alert(violation_details: Dict[str, Any],
                                    request_context: Dict[str, Any],
                                    trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Convenience function to emit policy violation alerts"""
    siem = get_siem_integration()
    
    alert = SecurityAlert(
        severity=AlertSeverity.HIGH,
        category=AlertCategory.POLICY_VIOLATION,
        event_type="hel_policy_violation",
        tenant_id=request_context.get("tenant_id", "unknown"),
        trace_id=trace_id,
        timestamp=str(int(time.time())),
        title=f"HEL Policy Violation: {violation_details.get('rule', 'unknown')}",
        description=violation_details.get("message", "Policy violation detected"),
        metadata=violation_details,
        source_ip=request_context.get("client_ip"),
        request_path=request_context.get("path"),
        request_method=request_context.get("method"),
        realm_id=request_context.get("realm_id"),
        agent_id=request_context.get("agent_id"),
        proof_kid=request_context.get("proof_kid")
    )
    
    return await siem.emit_security_alert(alert)

async def emit_authentication_failure_alert(failure_details: Dict[str, Any],
                                          request_context: Dict[str, Any],
                                          trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Convenience function to emit authentication failure alerts"""
    siem = get_siem_integration()
    
    alert = SecurityAlert(
        severity=AlertSeverity.MEDIUM,
        category=AlertCategory.AUTHENTICATION_FAILURE,
        event_type="authentication_failure",
        tenant_id=request_context.get("tenant_id", "unknown"),
        trace_id=trace_id,
        timestamp=str(int(time.time())),
        title="Authentication Failure",
        description=failure_details.get("message", "Authentication failed"),
        metadata=failure_details,
        source_ip=request_context.get("client_ip"),
        request_path=request_context.get("path"),
        request_method=request_context.get("method"),
        realm_id=request_context.get("realm_id"),
        agent_id=request_context.get("agent_id")
    )
    
    return await siem.emit_security_alert(alert)
