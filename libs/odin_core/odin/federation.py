"""
ODIN Federation & Settlement Service

Extends Roaming Pass with usage metering and settlement so vendors can 
charge each other per verified hop (interconnect/peering for AI).

Creates recurring, network-effect revenue where more orgs = more volume.
"""

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import uuid
from pathlib import Path

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False


class SettlementUnit(Enum):
    """Units for settlement billing."""
    REQUESTS = "requests"
    TOKENS = "tokens"
    BYTES = "bytes"
    MINUTES = "minutes"
    COMPUTE_UNITS = "compute_units"


class SettlementStatus(Enum):
    """Status of settlement periods."""
    ACTIVE = "active"
    PENDING_SETTLEMENT = "pending_settlement"
    SETTLED = "settled"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


@dataclass
class RoamingPassV2:
    """Enhanced roaming pass with settlement terms."""
    pass_id: str
    issuer_realm: str
    target_realm: str
    
    # Settlement terms
    unit_type: SettlementUnit
    rate_usd: Decimal  # Price per unit in USD
    vendor_id: str
    
    # Pass metadata
    expires_at: datetime
    issued_at: datetime
    capabilities: List[str]
    
    # Limits and constraints
    max_units: Optional[int] = None
    max_value_usd: Optional[Decimal] = None
    allowed_services: Optional[List[str]] = None
    
    # Status
    is_active: bool = True
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['unit_type'] = self.unit_type.value
        data['rate_usd'] = str(self.rate_usd)
        data['max_value_usd'] = str(self.max_value_usd) if self.max_value_usd else None
        data['expires_at'] = self.expires_at.isoformat()
        data['issued_at'] = self.issued_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoamingPassV2':
        """Create from dictionary."""
        data = data.copy()
        data['unit_type'] = SettlementUnit(data['unit_type'])
        data['rate_usd'] = Decimal(data['rate_usd'])
        data['max_value_usd'] = Decimal(data['max_value_usd']) if data.get('max_value_usd') else None
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        data['issued_at'] = datetime.fromisoformat(data['issued_at'])
        return cls(**data)


@dataclass
class BillingEvent:
    """Individual billing event for settlement."""
    event_id: str
    pass_id: str
    vendor_id: str
    counterparty_id: str
    
    # Usage details
    unit_type: SettlementUnit
    units: int
    rate_usd: Decimal
    total_usd: Decimal
    
    # Event metadata
    timestamp: datetime
    trace_id: str
    service: str
    realm: str
    
    # Processing status
    processed: bool = False
    settlement_period: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['unit_type'] = self.unit_type.value
        data['rate_usd'] = str(self.rate_usd)
        data['total_usd'] = str(self.total_usd)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BillingEvent':
        """Create from dictionary."""
        data = data.copy()
        data['unit_type'] = SettlementUnit(data['unit_type'])
        data['rate_usd'] = Decimal(data['rate_usd'])
        data['total_usd'] = Decimal(data['total_usd'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class SettlementPeriod:
    """Monthly settlement period between counterparties."""
    period_id: str
    start_date: datetime
    end_date: datetime
    
    # Counterparties
    payer_vendor_id: str
    payee_vendor_id: str
    
    # Financial summary
    total_events: int
    total_amount_usd: Decimal
    network_fee_usd: Decimal  # ODIN's cut (1-3%)
    net_amount_usd: Decimal
    
    # Status and processing
    status: SettlementStatus
    created_at: datetime
    settled_at: Optional[datetime] = None
    
    # Payment processing
    stripe_invoice_id: Optional[str] = None
    payment_method: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['start_date'] = self.start_date.isoformat()
        data['end_date'] = self.end_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['settled_at'] = self.settled_at.isoformat() if self.settled_at else None
        data['total_amount_usd'] = str(self.total_amount_usd)
        data['network_fee_usd'] = str(self.network_fee_usd)
        data['net_amount_usd'] = str(self.net_amount_usd)
        return data


@dataclass
class VendorProfile:
    """Vendor profile for federation and settlement."""
    vendor_id: str
    organization_name: str
    
    # Contact and billing
    billing_email: str
    technical_contact: str
    
    # Payment configuration
    stripe_customer_id: Optional[str] = None
    payment_terms_days: int = 30
    
    # Federation settings
    federation_enabled: bool = True
    auto_accept_passes: bool = False
    max_monthly_exposure_usd: Decimal = Decimal("10000")
    
    # Network fees
    network_fee_rate: Decimal = Decimal("0.025")  # 2.5% default
    
    # Status
    is_active: bool = True
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['max_monthly_exposure_usd'] = str(self.max_monthly_exposure_usd)
        data['network_fee_rate'] = str(self.network_fee_rate)
        data['created_at'] = self.created_at.isoformat()
        return data


class FederationStorage:
    """Storage backend for federation and settlement data."""
    
    def __init__(self, storage_path: str = "data/federation"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    # Roaming Pass V2 Storage
    async def store_roaming_pass(self, pass_v2: RoamingPassV2) -> bool:
        """Store roaming pass."""
        try:
            pass_file = self.storage_path / "passes" / f"{pass_v2.pass_id}.json"
            pass_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(pass_file, 'w') as f:
                json.dump(pass_v2.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store roaming pass: {e}")
            return False
    
    async def get_roaming_pass(self, pass_id: str) -> Optional[RoamingPassV2]:
        """Get roaming pass by ID."""
        try:
            pass_file = self.storage_path / "passes" / f"{pass_id}.json"
            if pass_file.exists():
                with open(pass_file, 'r') as f:
                    data = json.load(f)
                return RoamingPassV2.from_dict(data)
        except Exception as e:
            print(f"Failed to get roaming pass: {e}")
        return None
    
    # Billing Events Storage
    async def store_billing_event(self, event: BillingEvent) -> bool:
        """Store billing event."""
        try:
            # Store by month for efficient settlement processing
            month_key = event.timestamp.strftime("%Y-%m")
            event_file = self.storage_path / "events" / month_key / f"{event.event_id}.json"
            event_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(event_file, 'w') as f:
                json.dump(event.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store billing event: {e}")
            return False
    
    async def get_billing_events(self, start_date: datetime, end_date: datetime,
                                vendor_id: Optional[str] = None) -> List[BillingEvent]:
        """Get billing events for date range."""
        events = []
        
        try:
            # Iterate through months in range
            current = start_date.replace(day=1)
            while current <= end_date:
                month_key = current.strftime("%Y-%m")
                month_dir = self.storage_path / "events" / month_key
                
                if month_dir.exists():
                    for event_file in month_dir.glob("*.json"):
                        with open(event_file, 'r') as f:
                            data = json.load(f)
                        
                        event = BillingEvent.from_dict(data)
                        
                        # Filter by date range and vendor
                        if (start_date <= event.timestamp <= end_date and
                            (vendor_id is None or event.vendor_id == vendor_id)):
                            events.append(event)
                
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        
        except Exception as e:
            print(f"Failed to get billing events: {e}")
        
        return events
    
    # Settlement Periods Storage
    async def store_settlement_period(self, period: SettlementPeriod) -> bool:
        """Store settlement period."""
        try:
            period_file = self.storage_path / "settlements" / f"{period.period_id}.json"
            period_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(period_file, 'w') as f:
                json.dump(period.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store settlement period: {e}")
            return False
    
    async def get_settlement_periods(self, vendor_id: Optional[str] = None) -> List[SettlementPeriod]:
        """Get settlement periods."""
        periods = []
        
        try:
            settlements_dir = self.storage_path / "settlements"
            if settlements_dir.exists():
                for period_file in settlements_dir.glob("*.json"):
                    with open(period_file, 'r') as f:
                        data = json.load(f)
                    
                    period = SettlementPeriod(**data)
                    
                    # Filter by vendor if specified
                    if (vendor_id is None or 
                        period.payer_vendor_id == vendor_id or 
                        period.payee_vendor_id == vendor_id):
                        periods.append(period)
        
        except Exception as e:
            print(f"Failed to get settlement periods: {e}")
        
        return periods
    
    # Vendor Profiles Storage
    async def store_vendor_profile(self, profile: VendorProfile) -> bool:
        """Store vendor profile."""
        try:
            vendor_file = self.storage_path / "vendors" / f"{profile.vendor_id}.json"
            vendor_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(vendor_file, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store vendor profile: {e}")
            return False
    
    async def get_vendor_profile(self, vendor_id: str) -> Optional[VendorProfile]:
        """Get vendor profile."""
        try:
            vendor_file = self.storage_path / "vendors" / f"{vendor_id}.json"
            if vendor_file.exists():
                with open(vendor_file, 'r') as f:
                    data = json.load(f)
                return VendorProfile(**data)
        except Exception as e:
            print(f"Failed to get vendor profile: {e}")
        return None


class FederationMetering:
    """Handles usage metering for federation."""
    
    def __init__(self, storage: FederationStorage):
        self.storage = storage
    
    async def record_usage(self, pass_id: str, units: int, 
                          service: str, trace_id: str) -> Optional[BillingEvent]:
        """Record usage for a roaming pass."""
        try:
            # Get the pass
            roaming_pass = await self.storage.get_roaming_pass(pass_id)
            if not roaming_pass or not roaming_pass.is_active:
                return None
            
            # Check if pass has expired
            if datetime.now(timezone.utc) > roaming_pass.expires_at:
                return None
            
            # Calculate billing
            total_usd = Decimal(str(units)) * roaming_pass.rate_usd
            
            # Create billing event
            event = BillingEvent(
                event_id=str(uuid.uuid4()),
                pass_id=pass_id,
                vendor_id=roaming_pass.vendor_id,
                counterparty_id=roaming_pass.issuer_realm,  # Who pays
                unit_type=roaming_pass.unit_type,
                units=units,
                rate_usd=roaming_pass.rate_usd,
                total_usd=total_usd,
                timestamp=datetime.now(timezone.utc),
                trace_id=trace_id,
                service=service,
                realm=roaming_pass.target_realm
            )
            
            # Store event
            await self.storage.store_billing_event(event)
            
            # Update pass usage
            roaming_pass.usage_count += 1
            await self.storage.store_roaming_pass(roaming_pass)
            
            print(f"💰 Recorded usage: {units} {roaming_pass.unit_type.value} = ${total_usd}")
            
            return event
            
        except Exception as e:
            print(f"Failed to record usage: {e}")
            return None


class SettlementService:
    """Handles monthly settlement between vendors."""
    
    def __init__(self, storage: FederationStorage):
        self.storage = storage
        self.network_fee_rate = Decimal(os.getenv("ODIN_NETWORK_FEE_RATE", "0.025"))  # 2.5%
        
        # Initialize Stripe if available
        self.stripe_enabled = STRIPE_AVAILABLE and os.getenv("STRIPE_SECRET_KEY")
        if self.stripe_enabled:
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    async def process_monthly_settlement(self, year: int, month: int) -> List[SettlementPeriod]:
        """Process settlement for a specific month."""
        try:
            print(f"📊 Processing settlement for {year}-{month:02d}")
            
            # Get date range for month
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            
            # Get all billing events for the month
            events = await self.storage.get_billing_events(start_date, end_date)
            
            # Group events by counterparty pairs
            counterparty_pairs = {}
            for event in events:
                if event.processed:
                    continue
                
                # Create bidirectional key (smaller vendor_id first for consistency)
                pair_key = tuple(sorted([event.vendor_id, event.counterparty_id]))
                
                if pair_key not in counterparty_pairs:
                    counterparty_pairs[pair_key] = []
                counterparty_pairs[pair_key].append(event)
            
            # Create settlement periods
            settlement_periods = []
            
            for (vendor_a, vendor_b), pair_events in counterparty_pairs.items():
                # Separate events by direction
                a_to_b_events = [e for e in pair_events if e.vendor_id == vendor_a]
                b_to_a_events = [e for e in pair_events if e.vendor_id == vendor_b]
                
                # Calculate net amounts
                a_owes = sum(e.total_usd for e in a_to_b_events)
                b_owes = sum(e.total_usd for e in b_to_a_events)
                
                # Determine net settlement
                if a_owes > b_owes:
                    net_amount = a_owes - b_owes
                    payer = vendor_a
                    payee = vendor_b
                elif b_owes > a_owes:
                    net_amount = b_owes - a_owes
                    payer = vendor_b
                    payee = vendor_a
                else:
                    # No net payment needed
                    continue
                
                # Apply network fee
                network_fee = net_amount * self.network_fee_rate
                final_amount = net_amount - network_fee
                
                # Create settlement period
                period = SettlementPeriod(
                    period_id=f"{year}-{month:02d}_{payer}_{payee}",
                    start_date=start_date,
                    end_date=end_date,
                    payer_vendor_id=payer,
                    payee_vendor_id=payee,
                    total_events=len(pair_events),
                    total_amount_usd=net_amount,
                    network_fee_usd=network_fee,
                    net_amount_usd=final_amount,
                    status=SettlementStatus.PENDING_SETTLEMENT,
                    created_at=datetime.now(timezone.utc)
                )
                
                # Store settlement period
                await self.storage.store_settlement_period(period)
                settlement_periods.append(period)
                
                # Mark events as processed
                for event in pair_events:
                    event.processed = True
                    event.settlement_period = period.period_id
                    await self.storage.store_billing_event(event)
                
                print(f"💳 Created settlement: {payer} pays {payee} ${final_amount} (net: ${net_amount}, fee: ${network_fee})")
            
            return settlement_periods
            
        except Exception as e:
            print(f"Failed to process monthly settlement: {e}")
            return []
    
    async def create_stripe_invoice(self, period: SettlementPeriod) -> bool:
        """Create Stripe invoice for settlement."""
        if not self.stripe_enabled:
            print("Stripe not enabled, skipping invoice creation")
            return False
        
        try:
            # Get payer's Stripe customer
            payer_profile = await self.storage.get_vendor_profile(period.payer_vendor_id)
            if not payer_profile or not payer_profile.stripe_customer_id:
                print(f"No Stripe customer for {period.payer_vendor_id}")
                return False
            
            # Create invoice
            invoice = stripe.Invoice.create(
                customer=payer_profile.stripe_customer_id,
                collection_method='send_invoice',
                days_until_due=payer_profile.payment_terms_days,
                metadata={
                    'settlement_period_id': period.period_id,
                    'payee_vendor_id': period.payee_vendor_id,
                    'network_fee_usd': str(period.network_fee_usd)
                }
            )
            
            # Add line item
            stripe.InvoiceItem.create(
                customer=payer_profile.stripe_customer_id,
                invoice=invoice.id,
                amount=int(period.net_amount_usd * 100),  # Convert to cents
                currency='usd',
                description=f"ODIN Federation Settlement - {period.start_date.strftime('%Y-%m')}"
            )
            
            # Finalize and send
            stripe.Invoice.finalize_invoice(invoice.id)
            
            # Update settlement period
            period.stripe_invoice_id = invoice.id
            await self.storage.store_settlement_period(period)
            
            print(f"📧 Created Stripe invoice {invoice.id} for {period.payer_vendor_id}")
            return True
            
        except Exception as e:
            print(f"Failed to create Stripe invoice: {e}")
            return False


class FederationService:
    """Main federation and settlement service."""
    
    def __init__(self, storage: Optional[FederationStorage] = None):
        self.storage = storage or FederationStorage()
        self.metering = FederationMetering(self.storage)
        self.settlement = SettlementService(self.storage)
        
        # Background tasks
        self._settlement_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start federation service."""
        print("🤝 Starting ODIN Federation & Settlement Service")
        
        # Start monthly settlement task
        self._settlement_task = asyncio.create_task(self._monthly_settlement_runner())
        
        print("✅ Federation service started")
    
    async def stop(self):
        """Stop federation service."""
        if self._settlement_task:
            self._settlement_task.cancel()
            try:
                await self._settlement_task
            except asyncio.CancelledError:
                pass
        
        print("✅ Federation service stopped")
    
    async def create_roaming_pass_v2(self, issuer_realm: str, target_realm: str,
                                   unit_type: SettlementUnit, rate_usd: Decimal,
                                   vendor_id: str, **kwargs) -> RoamingPassV2:
        """Create enhanced roaming pass with settlement terms."""
        pass_v2 = RoamingPassV2(
            pass_id=str(uuid.uuid4()),
            issuer_realm=issuer_realm,
            target_realm=target_realm,
            unit_type=unit_type,
            rate_usd=rate_usd,
            vendor_id=vendor_id,
            expires_at=kwargs.get('expires_at', datetime.now(timezone.utc) + timedelta(days=30)),
            issued_at=datetime.now(timezone.utc),
            capabilities=kwargs.get('capabilities', []),
            max_units=kwargs.get('max_units'),
            max_value_usd=kwargs.get('max_value_usd'),
            allowed_services=kwargs.get('allowed_services')
        )
        
        await self.storage.store_roaming_pass(pass_v2)
        return pass_v2
    
    async def register_vendor(self, vendor_id: str, organization_name: str,
                            billing_email: str, technical_contact: str) -> VendorProfile:
        """Register new vendor for federation."""
        profile = VendorProfile(
            vendor_id=vendor_id,
            organization_name=organization_name,
            billing_email=billing_email,
            technical_contact=technical_contact
        )
        
        await self.storage.store_vendor_profile(profile)
        return profile
    
    async def record_federation_usage(self, pass_id: str, units: int,
                                    service: str, trace_id: str) -> bool:
        """Record usage for federation billing."""
        event = await self.metering.record_usage(pass_id, units, service, trace_id)
        return event is not None
    
    async def get_federation_stats(self) -> Dict[str, Any]:
        """Get federation statistics."""
        try:
            # Get current month events
            now = datetime.now(timezone.utc)
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            events = await self.storage.get_billing_events(start_of_month, now)
            
            # Calculate stats
            total_volume = sum(e.total_usd for e in events)
            total_events = len(events)
            unique_vendors = len(set(e.vendor_id for e in events))
            
            return {
                "current_month_volume_usd": str(total_volume),
                "current_month_events": total_events,
                "active_vendors": unique_vendors,
                "federation_status": "operational"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "federation_status": "degraded"
            }
    
    async def _monthly_settlement_runner(self):
        """Background task for monthly settlement processing."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                
                # Run settlement on 1st of month at 2 AM UTC
                if now.day == 1 and now.hour == 2 and now.minute < 5:
                    # Process previous month
                    if now.month == 1:
                        prev_year = now.year - 1
                        prev_month = 12
                    else:
                        prev_year = now.year
                        prev_month = now.month - 1
                    
                    await self.settlement.process_monthly_settlement(prev_year, prev_month)
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Settlement runner error: {e}")
                await asyncio.sleep(3600)  # Sleep 1 hour on error


# Global federation service
_federation_service: Optional[FederationService] = None


async def get_federation_service() -> FederationService:
    """Get global federation service."""
    global _federation_service
    if not _federation_service:
        _federation_service = FederationService()
        await _federation_service.start()
    return _federation_service


# Health check for federation
async def federation_health_check() -> Dict[str, Any]:
    """Check federation health."""
    try:
        federation = await get_federation_service()
        stats = await federation.get_federation_stats()
        
        return {
            "status": "healthy" if stats.get("federation_status") == "operational" else "degraded",
            "message": "Federation operational" if stats.get("federation_status") == "operational" else "Federation degraded",
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Federation health check failed: {e}",
            "stats": {}
        }
