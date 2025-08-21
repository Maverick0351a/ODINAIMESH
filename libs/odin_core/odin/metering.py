"""
Per-hop Metering & Settlement for ODIN Protocol

Extends receipts with billing.units + Stripe usage events; auto revenue share for Marketplace realm/maps.
Provides granular metering for AI operations, data transfer, and marketplace revenue distribution.
"""

from __future__ import annotations

import os
import math
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from decimal import Decimal
import logging

# Import existing billing system
from billing.usage import GLOBAL_BILLING_REPO, report_usage, calc_overage_units

try:
    import stripe  # type: ignore
    HAS_STRIPE = True
except ImportError:
    stripe = None
    HAS_STRIPE = False

_log = logging.getLogger(__name__)

@dataclass
class MeteringUnit:
    """
    Billing unit for a single hop/operation.
    
    Represents the cost components of an ODIN operation for marketplace billing.
    """
    operation: str  # envelope, transform, bridge, stream, vai_validation
    base_cost: float = 1.0  # Base operation cost in billing units
    compute_cost: float = 0.0  # Additional compute overhead
    data_transfer_mb: float = 0.0  # Data transfer volume
    storage_operations: int = 0  # Storage reads/writes
    ai_model_tokens: Optional[int] = None  # AI model token usage
    ai_model_type: Optional[str] = None  # gpt-4, claude-3, etc.
    
    def to_billing_units(self) -> float:
        """
        Convert to billable units using tiered pricing.
        
        Base pricing model:
        - 1 unit = 1000 requests baseline
        - AI tokens: 0.1 units per 1k tokens
        - Data transfer: 0.01 units per MB
        - Premium models: 2x multiplier
        """
        total_cost = self.base_cost
        
        # Add AI model token costs
        if self.ai_model_tokens:
            token_cost = (self.ai_model_tokens / 1000) * 0.1
            
            # Premium model multiplier
            if self.ai_model_type and self._is_premium_model(self.ai_model_type):
                token_cost *= 2.0
                
            total_cost += token_cost
            
        # Add data transfer costs
        if self.data_transfer_mb > 1:  # First MB free
            total_cost += (self.data_transfer_mb - 1) * 0.01
            
        # Add storage operation costs
        if self.storage_operations > 0:
            total_cost += self.storage_operations * 0.001  # 0.001 units per storage op
            
        # Add compute overhead
        total_cost += self.compute_cost
        
        return round(total_cost, 6)  # 6 decimal precision for micro-billing
    
    def _is_premium_model(self, model_type: str) -> bool:
        """Check if model is premium tier (higher billing rate)"""
        premium_models = {
            "gpt-4", "gpt-4-turbo", "claude-3-opus", "claude-3-sonnet",
            "gemini-pro", "command-r-plus"
        }
        return any(premium in model_type.lower() for premium in premium_models)

@dataclass
class RevenueShare:
    """Revenue distribution for marketplace participants"""
    platform: float  # ODIN platform fee
    provider: float  # Service provider share
    realm: float     # Realm owner share
    map_creator: Optional[float] = None  # SFT map creator share
    
    def total(self) -> float:
        """Calculate total revenue share (should equal billing amount)"""
        return self.platform + self.provider + self.realm + (self.map_creator or 0)

class RevenueShareCalculator:
    """Calculate marketplace revenue splits with configurable rates"""
    
    def __init__(self):
        # Configurable revenue share rates
        self.platform_fee = float(os.getenv("ODIN_PLATFORM_FEE", "0.10"))      # 10% platform fee
        self.realm_share = float(os.getenv("ODIN_REALM_SHARE", "0.15"))        # 15% to realm owner
        self.map_share = float(os.getenv("ODIN_MAP_SHARE", "0.05"))            # 5% to SFT map creator
        self.unit_price = float(os.getenv("ODIN_UNIT_PRICE", "0.001"))         # $0.001 per unit
    
    def calculate_shares(self, 
                        billing_units: float, 
                        realm_id: str, 
                        map_id: Optional[str] = None,
                        provider_id: Optional[str] = None) -> RevenueShare:
        """Calculate revenue shares for a billing event"""
        total_revenue = billing_units * self.unit_price
        
        platform_amount = total_revenue * self.platform_fee
        realm_amount = total_revenue * self.realm_share
        
        # Calculate provider share (remainder after platform and realm)
        provider_amount = total_revenue * (1 - self.platform_fee - self.realm_share)
        
        # If SFT map is used, map creator gets a cut from provider share
        map_creator_amount = None
        if map_id:
            map_creator_amount = total_revenue * self.map_share
            provider_amount -= map_creator_amount
            
        return RevenueShare(
            platform=round(platform_amount, 6),
            provider=round(provider_amount, 6),
            realm=round(realm_amount, 6),
            map_creator=round(map_creator_amount, 6) if map_creator_amount else None
        )
    
    def get_stripe_usage_records(self, 
                               shares: RevenueShare,
                               subscription_items: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate Stripe usage records for revenue distribution.
        
        Args:
            shares: Calculated revenue shares
            subscription_items: Mapping of {participant: subscription_item_id}
        """
        usage_records = []
        
        # Platform usage record (always included)
        if "platform" in subscription_items and shares.platform > 0:
            usage_records.append({
                "subscription_item": subscription_items["platform"],
                "quantity": math.ceil(shares.platform * 1000),  # Convert to units
                "action": "increment",
                "timestamp": int(time.time())
            })
        
        # Provider usage record
        if "provider" in subscription_items and shares.provider > 0:
            usage_records.append({
                "subscription_item": subscription_items["provider"],
                "quantity": math.ceil(shares.provider * 1000),
                "action": "increment",
                "timestamp": int(time.time())
            })
        
        # Realm owner usage record
        if "realm" in subscription_items and shares.realm > 0:
            usage_records.append({
                "subscription_item": subscription_items["realm"],
                "quantity": math.ceil(shares.realm * 1000),
                "action": "increment",
                "timestamp": int(time.time())
            })
        
        # Map creator usage record (if applicable)
        if shares.map_creator and "map_creator" in subscription_items:
            usage_records.append({
                "subscription_item": subscription_items["map_creator"],
                "quantity": math.ceil(shares.map_creator * 1000),
                "action": "increment",
                "timestamp": int(time.time())
            })
        
        return usage_records

class PerHopMeteringService:
    """Service for per-hop metering and settlement"""
    
    def __init__(self):
        self.enabled = os.getenv("ODIN_METERING_ENABLED", "0") == "1"
        self.calculator = RevenueShareCalculator()
        self.auto_report = os.getenv("ODIN_AUTO_REPORT_USAGE", "1") == "1"
        
    def create_metering_unit(self, 
                           operation: str,
                           request_data: Dict[str, Any],
                           response_data: Optional[Dict[str, Any]] = None,
                           sbom_info: Optional[Any] = None) -> MeteringUnit:
        """
        Create a metering unit from request/response data.
        
        Automatically extracts cost components from operation context.
        """
        unit = MeteringUnit(operation=operation)
        
        # Calculate data transfer
        request_size = len(str(request_data).encode('utf-8')) if request_data else 0
        response_size = len(str(response_data).encode('utf-8')) if response_data else 0
        unit.data_transfer_mb = (request_size + response_size) / (1024 * 1024)
        
        # Extract AI model information from SBOM
        if sbom_info:
            # Handle both SBOMInfo objects and dict formats
            if hasattr(sbom_info, 'models'):
                models = sbom_info.models
            elif isinstance(sbom_info, dict):
                models = sbom_info.get("models", [])
            else:
                models = []
                
            if models:
                unit.ai_model_type = models[0]  # Use first model for billing
                
                # Estimate token usage (rough heuristic)
                if response_data:
                    # Rough estimate: ~1 token per 4 characters for text
                    text_content = str(response_data)
                    unit.ai_model_tokens = len(text_content) // 4
        
        # Add operation-specific costs
        if operation == "envelope":
            unit.base_cost = 1.0
            unit.storage_operations = 1  # Writing receipt
        elif operation == "bridge":
            unit.base_cost = 2.0  # Higher cost for cross-realm operations
            unit.compute_cost = 0.5
            unit.storage_operations = 2  # Read + write transform receipts
        elif operation == "transform":
            unit.base_cost = 1.5
            unit.compute_cost = 0.3
            unit.storage_operations = 1
        elif operation == "vai_validation":
            unit.base_cost = 0.1  # Low cost for validation
        elif operation == "stream":
            unit.base_cost = 0.5  # Per-chunk cost
            unit.storage_operations = 1
        else:
            unit.base_cost = 1.0  # Default cost
            
        return unit
    
    def enhance_receipt_with_billing(self, 
                                   receipt: Dict[str, Any],
                                   metering_unit: MeteringUnit,
                                   realm_id: str,
                                   map_id: Optional[str] = None,
                                   provider_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Enhance receipt with billing information.
        
        Adds billing.units and billing.revenue_shares to receipt.
        """
        if not self.enabled:
            return receipt
        
        billing_units = metering_unit.to_billing_units()
        revenue_shares = self.calculator.calculate_shares(
            billing_units, realm_id, map_id, provider_id
        )
        
        # Add billing section to receipt
        receipt["billing"] = {
            "units": billing_units,
            "operation": metering_unit.operation,
            "pricing": {
                "unit_price_usd": self.calculator.unit_price,
                "total_usd": billing_units * self.calculator.unit_price
            },
            "revenue_shares": {
                "platform": revenue_shares.platform,
                "provider": revenue_shares.provider,
                "realm": revenue_shares.realm,
                "map_creator": revenue_shares.map_creator
            },
            "metering_details": {
                "base_cost": metering_unit.base_cost,
                "compute_cost": metering_unit.compute_cost,
                "data_transfer_mb": metering_unit.data_transfer_mb,
                "storage_operations": metering_unit.storage_operations,
                "ai_model_tokens": metering_unit.ai_model_tokens,
                "ai_model_type": metering_unit.ai_model_type
            }
        }
        
        return receipt
    
    async def report_usage_to_stripe(self, 
                                   receipt: Dict[str, Any],
                                   tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Report usage to Stripe for billing.
        
        Returns list of created usage records.
        """
        if not self.enabled or not self.auto_report or not HAS_STRIPE:
            return None
        
        billing_info = receipt.get("billing")
        if not billing_info:
            return None
        
        try:
            # Get subscription items for this tenant
            subscription_items = self._get_tenant_subscription_items(tenant_id)
            if not subscription_items:
                _log.warning(f"No subscription items found for tenant {tenant_id}")
                return None
            
            # Create revenue shares object
            shares_data = billing_info["revenue_shares"]
            shares = RevenueShare(
                platform=shares_data["platform"],
                provider=shares_data["provider"],
                realm=shares_data["realm"],
                map_creator=shares_data.get("map_creator")
            )
            
            # Generate usage records
            usage_records_data = self.calculator.get_stripe_usage_records(
                shares, subscription_items
            )
            
            # Submit to Stripe
            created_records = []
            for record_data in usage_records_data:
                try:
                    if HAS_STRIPE and stripe:
                        record = stripe.UsageRecord.create(**record_data)
                        created_records.append(record)
                except Exception as e:
                    _log.error(f"Failed to create Stripe usage record: {e}")
            
            return created_records
            
        except Exception as e:
            _log.error(f"Failed to report usage to Stripe: {e}")
            return None
    
    def _get_tenant_subscription_items(self, tenant_id: str) -> Optional[Dict[str, str]]:
        """Get subscription item IDs for tenant's revenue distribution"""
        # This would be implemented based on your tenant subscription model
        # For now, return a mock structure
        return {
            "platform": f"si_platform_{tenant_id}",
            "provider": f"si_provider_{tenant_id}",
            "realm": f"si_realm_{tenant_id}",
            "map_creator": f"si_map_{tenant_id}"
        }

# Global service instance
_global_metering_service: Optional[PerHopMeteringService] = None

def get_metering_service() -> PerHopMeteringService:
    """Get or create the global metering service instance"""
    global _global_metering_service
    if _global_metering_service is None:
        _global_metering_service = PerHopMeteringService()
    return _global_metering_service

def create_operation_billing(operation: str,
                           request_data: Dict[str, Any],
                           response_data: Optional[Dict[str, Any]] = None,
                           sbom_info: Optional[Dict[str, Any]] = None) -> MeteringUnit:
    """Convenience function to create billing for an operation"""
    service = get_metering_service()
    return service.create_metering_unit(operation, request_data, response_data, sbom_info)

def enhance_receipt_with_marketplace_billing(receipt: Dict[str, Any],
                                           metering_unit: MeteringUnit,
                                           realm_id: str,
                                           map_id: Optional[str] = None,
                                           provider_id: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to enhance receipt with marketplace billing"""
    service = get_metering_service()
    return service.enhance_receipt_with_billing(receipt, metering_unit, realm_id, map_id, provider_id)

async def auto_report_stripe_usage(receipt: Dict[str, Any], tenant_id: str) -> Optional[List[Dict[str, Any]]]:
    """Convenience function to auto-report usage to Stripe"""
    service = get_metering_service()
    return await service.report_usage_to_stripe(receipt, tenant_id)

def track_billable_event(event_type: str, 
                         tenant_id: str, 
                         amount: float, 
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Track a billable event for revenue reporting and analytics"""
    import time
    from datetime import datetime, timezone
    
    event_data = {
        "event_id": f"{event_type}_{tenant_id}_{int(time.time() * 1000)}",
        "event_type": event_type,
        "tenant_id": tenant_id,
        "amount": amount,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {}
    }
    
    # In production, this would be sent to analytics/billing system
    # For now, return the event data for logging
    return event_data

def get_usage_metrics(tenant_id: Optional[str] = None, 
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get usage metrics for billing and analytics"""
    from datetime import datetime, timezone, timedelta
    
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = datetime.now(timezone.utc).isoformat()
    
    # Mock metrics data - in production this would query the actual usage database
    metrics = {
        "tenant_id": tenant_id,
        "period": {
            "start": start_date,
            "end": end_date
        },
        "usage_summary": {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "services_used": []
        },
        "billing_summary": {
            "billable_events": 0,
            "total_revenue": 0.0,
            "currency": "USD"
        }
    }
    
    return metrics
