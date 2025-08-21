"""
Payments Bridge Pro API

REST endpoints for enterprise payment processing with direct bank integration.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid

from odin.payments_bridge_pro import (
    PaymentsBridgeProService, get_payments_service,
    EnterprisePayment, PaymentBatch, BankProfile,
    BankingProtocol, PaymentStatus, TransferMethod,
    payments_health_check
)

router = APIRouter(prefix="/v1/payments", tags=["payments"])


# Request/Response Models

class CreatePaymentRequest(BaseModel):
    """Request to create enterprise payment."""
    amount_usd: str = Field(..., description="Payment amount in USD")
    payee_name: str = Field(..., description="Payee name")
    payee_account: str = Field(..., description="Payee account number")
    payee_routing: str = Field(..., description="Payee routing number")
    payee_bank_name: str = Field("", description="Payee bank name")
    description: str = Field(..., description="Payment description")
    bank_profile_id: str = Field(..., description="Bank profile to use")
    reference_number: Optional[str] = Field(None, description="Payment reference")
    payer_name: str = Field("ODIN Client", description="Payer name")
    payer_account: str = Field("", description="Payer account")
    payer_routing: str = Field("", description="Payer routing")
    protocol: str = Field("ach_nacha", description="Banking protocol")


class PaymentResponse(BaseModel):
    """Payment response."""
    payment_id: str
    amount_usd: str
    currency: str
    payee_name: str
    payee_account: str
    payee_routing: str
    payee_bank_name: str
    description: str
    reference_number: str
    bank_profile_id: str
    protocol: str
    transfer_method: str
    status: str
    created_at: str
    submitted_at: Optional[str]
    completed_at: Optional[str]
    bank_reference: Optional[str]
    trace_number: Optional[str]
    
    @classmethod
    def from_payment(cls, payment: EnterprisePayment) -> 'PaymentResponse':
        """Create response from payment."""
        return cls(
            payment_id=payment.payment_id,
            amount_usd=str(payment.amount_usd),
            currency=payment.currency,
            payee_name=payment.payee_name,
            payee_account=payment.payee_account,
            payee_routing=payment.payee_routing,
            payee_bank_name=payment.payee_bank_name,
            description=payment.description,
            reference_number=payment.reference_number,
            bank_profile_id=payment.bank_profile_id,
            protocol=payment.protocol.value,
            transfer_method=payment.transfer_method.value,
            status=payment.status.value,
            created_at=payment.created_at.isoformat(),
            submitted_at=payment.submitted_at.isoformat() if payment.submitted_at else None,
            completed_at=payment.completed_at.isoformat() if payment.completed_at else None,
            bank_reference=payment.bank_reference,
            trace_number=payment.trace_number
        )


class CreateBankProfileRequest(BaseModel):
    """Request to create bank profile."""
    bank_id: str = Field(..., description="Bank identifier")
    bank_name: str = Field(..., description="Bank name")
    supported_protocols: List[str] = Field(..., description="Supported protocols")
    preferred_protocol: str = Field(..., description="Preferred protocol")
    sftp_host: Optional[str] = Field(None, description="SFTP host")
    sftp_port: int = Field(22, description="SFTP port")
    sftp_username: Optional[str] = Field(None, description="SFTP username")
    sftp_directory: str = Field("/incoming", description="SFTP directory")
    api_endpoint: Optional[str] = Field(None, description="API endpoint")
    file_format: str = Field("xml", description="File format")
    encoding: str = Field("utf-8", description="File encoding")
    batch_size_limit: int = Field(1000, description="Batch size limit")
    daily_limit_usd: str = Field("10000000", description="Daily limit USD")
    cut_off_time: str = Field("15:00", description="Cut-off time")


class BankProfileResponse(BaseModel):
    """Bank profile response."""
    bank_id: str
    bank_name: str
    supported_protocols: List[str]
    preferred_protocol: str
    sftp_host: Optional[str]
    sftp_port: int
    sftp_username: Optional[str]
    sftp_directory: str
    api_endpoint: Optional[str]
    file_format: str
    encoding: str
    batch_size_limit: int
    daily_limit_usd: str
    cut_off_time: str
    statement_schedule: str
    statement_format: str
    is_active: bool
    created_at: str
    
    @classmethod
    def from_bank_profile(cls, profile: BankProfile) -> 'BankProfileResponse':
        """Create response from bank profile."""
        return cls(
            bank_id=profile.bank_id,
            bank_name=profile.bank_name,
            supported_protocols=[p.value for p in profile.supported_protocols],
            preferred_protocol=profile.preferred_protocol.value,
            sftp_host=profile.sftp_host,
            sftp_port=profile.sftp_port,
            sftp_username=profile.sftp_username,
            sftp_directory=profile.sftp_directory,
            api_endpoint=profile.api_endpoint,
            file_format=profile.file_format,
            encoding=profile.encoding,
            batch_size_limit=profile.batch_size_limit,
            daily_limit_usd=str(profile.daily_limit_usd),
            cut_off_time=profile.cut_off_time,
            statement_schedule=profile.statement_schedule,
            statement_format=profile.statement_format.value,
            is_active=profile.is_active,
            created_at=profile.created_at.isoformat()
        )


class BatchPaymentRequest(BaseModel):
    """Request to process payment batch."""
    payment_ids: List[str] = Field(..., description="Payment IDs to batch")
    bank_profile_id: str = Field(..., description="Bank profile to use")


class BatchResponse(BaseModel):
    """Batch response."""
    batch_id: str
    bank_profile_id: str
    payment_count: int
    total_amount_usd: str
    protocol: str
    transfer_method: str
    status: str
    created_at: str
    submitted_at: Optional[str]
    output_filename: Optional[str]
    file_hash: Optional[str]
    
    @classmethod
    def from_batch(cls, batch: PaymentBatch) -> 'BatchResponse':
        """Create response from batch."""
        return cls(
            batch_id=batch.batch_id,
            bank_profile_id=batch.bank_profile_id,
            payment_count=batch.payment_count,
            total_amount_usd=str(batch.total_amount_usd),
            protocol=batch.protocol.value,
            transfer_method=batch.transfer_method.value,
            status=batch.status.value,
            created_at=batch.created_at.isoformat(),
            submitted_at=batch.submitted_at.isoformat() if batch.submitted_at else None,
            output_filename=batch.output_filename,
            file_hash=batch.file_hash
        )


# Health Check
@router.get("/health",
    summary="Payments Health Check",
    description="Check Payments Bridge Pro service health")
async def payments_health() -> Dict[str, Any]:
    """Check payments service health."""
    return await payments_health_check()


# Bank Profile Management
@router.post("/banks",
    response_model=BankProfileResponse,
    summary="Create Bank Profile",
    description="Create new bank profile for payment processing")
async def create_bank_profile(
    request: CreateBankProfileRequest,
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> BankProfileResponse:
    """Create bank profile."""
    try:
        # Check if bank already exists
        existing = await payments.storage.get_bank_profile(request.bank_id)
        if existing:
            raise HTTPException(status_code=409, detail="Bank profile already exists")
        
        # Validate protocols
        try:
            supported_protocols = [BankingProtocol(p) for p in request.supported_protocols]
            preferred_protocol = BankingProtocol(request.preferred_protocol)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid protocol: {e}")
        
        # Create profile
        profile = BankProfile(
            bank_id=request.bank_id,
            bank_name=request.bank_name,
            supported_protocols=supported_protocols,
            preferred_protocol=preferred_protocol,
            sftp_host=request.sftp_host,
            sftp_port=request.sftp_port,
            sftp_username=request.sftp_username,
            sftp_directory=request.sftp_directory,
            api_endpoint=request.api_endpoint,
            file_format=request.file_format,
            encoding=request.encoding,
            batch_size_limit=request.batch_size_limit,
            daily_limit_usd=Decimal(request.daily_limit_usd),
            cut_off_time=request.cut_off_time
        )
        
        await payments.storage.store_bank_profile(profile)
        
        return BankProfileResponse.from_bank_profile(profile)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bank profile: {e}")


@router.get("/banks/{bank_id}",
    response_model=BankProfileResponse,
    summary="Get Bank Profile",
    description="Get bank profile by ID")
async def get_bank_profile(
    bank_id: str,
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> BankProfileResponse:
    """Get bank profile."""
    profile = await payments.storage.get_bank_profile(bank_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Bank profile not found")
    
    return BankProfileResponse.from_bank_profile(profile)


# Payment Management
@router.post("/create",
    response_model=PaymentResponse,
    summary="Create Payment",
    description="Create new enterprise payment")
async def create_payment(
    request: CreatePaymentRequest,
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> PaymentResponse:
    """Create enterprise payment."""
    try:
        # Validate protocol
        try:
            protocol = BankingProtocol(request.protocol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid protocol: {request.protocol}")
        
        # Validate bank profile exists
        bank_profile = await payments.storage.get_bank_profile(request.bank_profile_id)
        if not bank_profile:
            raise HTTPException(status_code=404, detail="Bank profile not found")
        
        # Create payment
        payment = await payments.create_enterprise_payment(
            amount_usd=Decimal(request.amount_usd),
            payee_name=request.payee_name,
            payee_account=request.payee_account,
            payee_routing=request.payee_routing,
            description=request.description,
            bank_profile_id=request.bank_profile_id,
            reference_number=request.reference_number,
            payer_name=request.payer_name,
            payer_account=request.payer_account,
            payer_routing=request.payer_routing,
            protocol=protocol
        )
        
        return PaymentResponse.from_payment(payment)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {e}")


@router.get("/payment/{payment_id}",
    response_model=PaymentResponse,
    summary="Get Payment",
    description="Get payment by ID")
async def get_payment(
    payment_id: str,
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> PaymentResponse:
    """Get payment by ID."""
    payment = await payments.storage.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return PaymentResponse.from_payment(payment)


# Batch Processing
@router.post("/batch",
    response_model=BatchResponse,
    summary="Process Payment Batch",
    description="Process batch of payments")
async def process_batch(
    request: BatchPaymentRequest,
    background_tasks: BackgroundTasks,
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> BatchResponse:
    """Process payment batch."""
    try:
        # Get payments
        payment_objects = []
        for payment_id in request.payment_ids:
            payment = await payments.storage.get_payment(payment_id)
            if not payment:
                raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
            
            if payment.status != PaymentStatus.PENDING:
                raise HTTPException(status_code=400, detail=f"Payment {payment_id} not in pending status")
            
            payment_objects.append(payment)
        
        # Validate bank profile
        bank_profile = await payments.storage.get_bank_profile(request.bank_profile_id)
        if not bank_profile:
            raise HTTPException(status_code=404, detail="Bank profile not found")
        
        # Process batch in background
        background_tasks.add_task(
            payments.process_payment_batch,
            payment_objects,
            request.bank_profile_id
        )
        
        # Create preliminary batch response
        batch_id = str(uuid.uuid4())
        
        return BatchResponse(
            batch_id=batch_id,
            bank_profile_id=request.bank_profile_id,
            payment_count=len(payment_objects),
            total_amount_usd=str(sum(p.amount_usd for p in payment_objects)),
            protocol=bank_profile.preferred_protocol.value,
            transfer_method=TransferMethod.SFTP.value,
            status=PaymentStatus.PROCESSING.value,
            created_at=datetime.now(timezone.utc).isoformat(),
            submitted_at=None,
            output_filename=None,
            file_hash=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process batch: {e}")


# Payment Statistics
@router.get("/stats",
    summary="Payment Statistics",
    description="Get payment processing statistics")
async def get_payment_stats(
    payments: PaymentsBridgeProService = Depends(get_payments_service)
) -> Dict[str, Any]:
    """Get payment statistics."""
    return await payments.get_payment_stats()


# Protocol Reference
@router.get("/protocols",
    summary="Get Banking Protocols",
    description="Get supported banking protocols")
async def get_protocols() -> Dict[str, Any]:
    """Get supported banking protocols."""
    return {
        "protocols": [protocol.value for protocol in BankingProtocol],
        "descriptions": {
            "ach_nacha": "ACH NACHA format for US domestic transfers",
            "wire_fedwire": "Fedwire format for US wire transfers",
            "swift_mt103": "SWIFT MT103 format for international wires",
            "iso20022_pain001": "ISO 20022 PAIN.001 format",
            "bai2": "BAI2 format for bank account reporting",
            "mt940": "SWIFT MT940 format for account statements",
            "csv_custom": "Custom CSV format"
        },
        "transfer_methods": [method.value for method in TransferMethod],
        "payment_statuses": [status.value for status in PaymentStatus]
    }
