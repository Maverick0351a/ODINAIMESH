"""
ODIN Federation API

REST endpoints for federation, roaming, and settlement.
Enables vendors to charge each other for AI traffic.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid

from odin.federation import (
    FederationService, get_federation_service,
    RoamingPassV2, SettlementUnit, VendorProfile,
    BillingEvent, SettlementPeriod, SettlementStatus,
    federation_health_check
)

router = APIRouter(prefix="/v1/federation", tags=["federation"])


# Request/Response Models

class CreateRoamingPassRequest(BaseModel):
    """Request to create roaming pass."""
    issuer_realm: str = Field(..., description="Realm issuing the pass")
    target_realm: str = Field(..., description="Target realm for access")
    unit_type: str = Field(..., description="Billing unit type")
    rate_usd: str = Field(..., description="Rate per unit in USD")
    vendor_id: str = Field(..., description="Vendor identifier")
    expires_days: int = Field(30, description="Days until expiration")
    capabilities: List[str] = Field(default_factory=list, description="Allowed capabilities")
    max_units: Optional[int] = Field(None, description="Maximum units allowed")
    max_value_usd: Optional[str] = Field(None, description="Maximum value in USD")
    allowed_services: Optional[List[str]] = Field(None, description="Allowed services")


class RoamingPassResponse(BaseModel):
    """Roaming pass response."""
    pass_id: str
    issuer_realm: str
    target_realm: str
    unit_type: str
    rate_usd: str
    vendor_id: str
    expires_at: str
    issued_at: str
    capabilities: List[str]
    max_units: Optional[int]
    max_value_usd: Optional[str]
    allowed_services: Optional[List[str]]
    is_active: bool
    usage_count: int
    
    @classmethod
    def from_roaming_pass(cls, pass_v2: RoamingPassV2) -> 'RoamingPassResponse':
        """Create response from roaming pass."""
        return cls(
            pass_id=pass_v2.pass_id,
            issuer_realm=pass_v2.issuer_realm,
            target_realm=pass_v2.target_realm,
            unit_type=pass_v2.unit_type.value,
            rate_usd=str(pass_v2.rate_usd),
            vendor_id=pass_v2.vendor_id,
            expires_at=pass_v2.expires_at.isoformat(),
            issued_at=pass_v2.issued_at.isoformat(),
            capabilities=pass_v2.capabilities,
            max_units=pass_v2.max_units,
            max_value_usd=str(pass_v2.max_value_usd) if pass_v2.max_value_usd else None,
            allowed_services=pass_v2.allowed_services,
            is_active=pass_v2.is_active,
            usage_count=pass_v2.usage_count
        )


class RegisterVendorRequest(BaseModel):
    """Request to register vendor."""
    vendor_id: str = Field(..., description="Unique vendor identifier")
    organization_name: str = Field(..., description="Organization name")
    billing_email: str = Field(..., description="Billing contact email")
    technical_contact: str = Field(..., description="Technical contact")
    payment_terms_days: int = Field(30, description="Payment terms in days")
    auto_accept_passes: bool = Field(False, description="Auto-accept roaming passes")
    max_monthly_exposure_usd: str = Field("10000", description="Max monthly exposure")


class VendorProfileResponse(BaseModel):
    """Vendor profile response."""
    vendor_id: str
    organization_name: str
    billing_email: str
    technical_contact: str
    stripe_customer_id: Optional[str]
    payment_terms_days: int
    federation_enabled: bool
    auto_accept_passes: bool
    max_monthly_exposure_usd: str
    network_fee_rate: str
    is_active: bool
    created_at: str
    
    @classmethod
    def from_vendor_profile(cls, profile: VendorProfile) -> 'VendorProfileResponse':
        """Create response from vendor profile."""
        return cls(
            vendor_id=profile.vendor_id,
            organization_name=profile.organization_name,
            billing_email=profile.billing_email,
            technical_contact=profile.technical_contact,
            stripe_customer_id=profile.stripe_customer_id,
            payment_terms_days=profile.payment_terms_days,
            federation_enabled=profile.federation_enabled,
            auto_accept_passes=profile.auto_accept_passes,
            max_monthly_exposure_usd=str(profile.max_monthly_exposure_usd),
            network_fee_rate=str(profile.network_fee_rate),
            is_active=profile.is_active,
            created_at=profile.created_at.isoformat()
        )


class UsageRecordRequest(BaseModel):
    """Request to record usage."""
    pass_id: str = Field(..., description="Roaming pass ID")
    units: int = Field(..., description="Number of units used")
    service: str = Field(..., description="Service name")
    trace_id: str = Field(..., description="Trace ID for tracking")


class BillingEventResponse(BaseModel):
    """Billing event response."""
    event_id: str
    pass_id: str
    vendor_id: str
    counterparty_id: str
    unit_type: str
    units: int
    rate_usd: str
    total_usd: str
    timestamp: str
    trace_id: str
    service: str
    realm: str
    processed: bool
    settlement_period: Optional[str]
    
    @classmethod
    def from_billing_event(cls, event: BillingEvent) -> 'BillingEventResponse':
        """Create response from billing event."""
        return cls(
            event_id=event.event_id,
            pass_id=event.pass_id,
            vendor_id=event.vendor_id,
            counterparty_id=event.counterparty_id,
            unit_type=event.unit_type.value,
            units=event.units,
            rate_usd=str(event.rate_usd),
            total_usd=str(event.total_usd),
            timestamp=event.timestamp.isoformat(),
            trace_id=event.trace_id,
            service=event.service,
            realm=event.realm,
            processed=event.processed,
            settlement_period=event.settlement_period
        )


class SettlementPeriodResponse(BaseModel):
    """Settlement period response."""
    period_id: str
    start_date: str
    end_date: str
    payer_vendor_id: str
    payee_vendor_id: str
    total_events: int
    total_amount_usd: str
    network_fee_usd: str
    net_amount_usd: str
    status: str
    created_at: str
    settled_at: Optional[str]
    stripe_invoice_id: Optional[str]
    payment_method: Optional[str]
    
    @classmethod
    def from_settlement_period(cls, period: SettlementPeriod) -> 'SettlementPeriodResponse':
        """Create response from settlement period."""
        return cls(
            period_id=period.period_id,
            start_date=period.start_date.isoformat(),
            end_date=period.end_date.isoformat(),
            payer_vendor_id=period.payer_vendor_id,
            payee_vendor_id=period.payee_vendor_id,
            total_events=period.total_events,
            total_amount_usd=str(period.total_amount_usd),
            network_fee_usd=str(period.network_fee_usd),
            net_amount_usd=str(period.net_amount_usd),
            status=period.status.value,
            created_at=period.created_at.isoformat(),
            settled_at=period.settled_at.isoformat() if period.settled_at else None,
            stripe_invoice_id=period.stripe_invoice_id,
            payment_method=period.payment_method
        )


# Federation Health
@router.get("/health", 
    summary="Federation Health Check",
    description="Check federation service health and operational status")
async def federation_health() -> Dict[str, Any]:
    """Check federation service health."""
    return await federation_health_check()


# Vendor Management
@router.post("/vendors/register",
    response_model=VendorProfileResponse,
    summary="Register Vendor",
    description="Register new vendor for federation and settlement")
async def register_vendor(
    request: RegisterVendorRequest,
    federation: FederationService = Depends(get_federation_service)
) -> VendorProfileResponse:
    """Register new vendor for federation."""
    try:
        # Check if vendor already exists
        existing = await federation.storage.get_vendor_profile(request.vendor_id)
        if existing:
            raise HTTPException(status_code=409, detail="Vendor already exists")
        
        # Create vendor profile
        profile = await federation.register_vendor(
            vendor_id=request.vendor_id,
            organization_name=request.organization_name,
            billing_email=request.billing_email,
            technical_contact=request.technical_contact
        )
        
        # Update additional settings
        profile.payment_terms_days = request.payment_terms_days
        profile.auto_accept_passes = request.auto_accept_passes
        profile.max_monthly_exposure_usd = Decimal(request.max_monthly_exposure_usd)
        
        await federation.storage.store_vendor_profile(profile)
        
        return VendorProfileResponse.from_vendor_profile(profile)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register vendor: {e}")


@router.get("/vendors/{vendor_id}",
    response_model=VendorProfileResponse,
    summary="Get Vendor Profile",
    description="Get vendor profile by ID")
async def get_vendor(
    vendor_id: str,
    federation: FederationService = Depends(get_federation_service)
) -> VendorProfileResponse:
    """Get vendor profile."""
    profile = await federation.storage.get_vendor_profile(vendor_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    return VendorProfileResponse.from_vendor_profile(profile)


# Roaming Pass Management
@router.post("/passes",
    response_model=RoamingPassResponse,
    summary="Create Roaming Pass",
    description="Create roaming pass with settlement terms")
async def create_roaming_pass(
    request: CreateRoamingPassRequest,
    federation: FederationService = Depends(get_federation_service)
) -> RoamingPassResponse:
    """Create roaming pass with settlement terms."""
    try:
        # Validate unit type
        try:
            unit_type = SettlementUnit(request.unit_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid unit type: {request.unit_type}")
        
        # Create pass
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_days)
        
        pass_v2 = await federation.create_roaming_pass_v2(
            issuer_realm=request.issuer_realm,
            target_realm=request.target_realm,
            unit_type=unit_type,
            rate_usd=Decimal(request.rate_usd),
            vendor_id=request.vendor_id,
            expires_at=expires_at,
            capabilities=request.capabilities,
            max_units=request.max_units,
            max_value_usd=Decimal(request.max_value_usd) if request.max_value_usd else None,
            allowed_services=request.allowed_services
        )
        
        return RoamingPassResponse.from_roaming_pass(pass_v2)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create roaming pass: {e}")


@router.get("/passes/{pass_id}",
    response_model=RoamingPassResponse,
    summary="Get Roaming Pass",
    description="Get roaming pass by ID")
async def get_roaming_pass(
    pass_id: str,
    federation: FederationService = Depends(get_federation_service)
) -> RoamingPassResponse:
    """Get roaming pass by ID."""
    pass_v2 = await federation.storage.get_roaming_pass(pass_id)
    if not pass_v2:
        raise HTTPException(status_code=404, detail="Roaming pass not found")
    
    return RoamingPassResponse.from_roaming_pass(pass_v2)


# Usage Recording
@router.post("/usage",
    summary="Record Usage",
    description="Record usage for federation billing")
async def record_usage(
    request: UsageRecordRequest,
    federation: FederationService = Depends(get_federation_service)
) -> Dict[str, Any]:
    """Record usage for federation billing."""
    try:
        success = await federation.record_federation_usage(
            pass_id=request.pass_id,
            units=request.units,
            service=request.service,
            trace_id=request.trace_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to record usage")
        
        return {
            "status": "recorded",
            "pass_id": request.pass_id,
            "units": request.units,
            "trace_id": request.trace_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record usage: {e}")


# Billing and Settlement
@router.get("/billing/events",
    response_model=List[BillingEventResponse],
    summary="Get Billing Events",
    description="Get billing events for date range")
async def get_billing_events(
    start_date: str,
    end_date: str,
    vendor_id: Optional[str] = None,
    federation: FederationService = Depends(get_federation_service)
) -> List[BillingEventResponse]:
    """Get billing events for date range."""
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        events = await federation.storage.get_billing_events(start_dt, end_dt, vendor_id)
        
        return [BillingEventResponse.from_billing_event(event) for event in events]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get billing events: {e}")


@router.get("/settlement/periods",
    response_model=List[SettlementPeriodResponse],
    summary="Get Settlement Periods",
    description="Get settlement periods for vendor")
async def get_settlement_periods(
    vendor_id: Optional[str] = None,
    federation: FederationService = Depends(get_federation_service)
) -> List[SettlementPeriodResponse]:
    """Get settlement periods."""
    try:
        periods = await federation.storage.get_settlement_periods(vendor_id)
        
        return [SettlementPeriodResponse.from_settlement_period(period) for period in periods]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settlement periods: {e}")


@router.post("/settlement/process",
    summary="Process Settlement",
    description="Process monthly settlement for specific period")
async def process_settlement(
    year: int,
    month: int,
    background_tasks: BackgroundTasks,
    federation: FederationService = Depends(get_federation_service)
) -> Dict[str, Any]:
    """Process monthly settlement."""
    try:
        # Validate date
        if not (1 <= month <= 12):
            raise HTTPException(status_code=400, detail="Invalid month")
        
        if not (2020 <= year <= 2030):
            raise HTTPException(status_code=400, detail="Invalid year")
        
        # Run settlement in background
        background_tasks.add_task(
            federation.settlement.process_monthly_settlement,
            year, month
        )
        
        return {
            "status": "processing",
            "year": year,
            "month": month,
            "message": f"Settlement processing started for {year}-{month:02d}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process settlement: {e}")


# Federation Statistics
@router.get("/stats",
    summary="Federation Statistics",
    description="Get federation service statistics")
async def get_federation_stats(
    federation: FederationService = Depends(get_federation_service)
) -> Dict[str, Any]:
    """Get federation statistics."""
    return await federation.get_federation_stats()


# Unit Types Reference
@router.get("/units",
    summary="Get Settlement Units",
    description="Get available settlement unit types")
async def get_settlement_units() -> Dict[str, List[str]]:
    """Get available settlement unit types."""
    return {
        "unit_types": [unit.value for unit in SettlementUnit],
        "descriptions": {
            "requests": "Per API request",
            "tokens": "Per token processed",
            "bytes": "Per byte transferred",
            "minutes": "Per minute of processing",
            "compute_units": "Per compute unit consumed"
        }
    }
