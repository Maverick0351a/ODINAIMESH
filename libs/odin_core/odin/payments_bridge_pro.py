"""
Payments Bridge Pro - Direct-to-Bank Connector

High-value B2B payment automation with bank-specific protocols,
SFTP integrations, and enterprise-grade reconciliation.

Targets Fortune 500 companies paying $50K-500K+ monthly.
"""

import asyncio
import csv
import json
import os
import paramiko
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import uuid
import hashlib

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False


class BankingProtocol(Enum):
    """Supported banking protocols."""
    ACH_NACHA = "ach_nacha"
    WIRE_FEDWIRE = "wire_fedwire"
    SWIFT_MT103 = "swift_mt103"
    ISO20022_PAIN001 = "iso20022_pain001"
    BAI2 = "bai2"
    MT940 = "mt940"
    CSV_CUSTOM = "csv_custom"


class PaymentStatus(Enum):
    """Payment status tracking."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RECONCILED = "reconciled"
    DISPUTED = "disputed"


class TransferMethod(Enum):
    """Transfer methods."""
    SFTP = "sftp"
    API = "api"
    EMAIL = "email"
    MANUAL = "manual"


@dataclass
class BankProfile:
    """Bank-specific configuration profile."""
    bank_id: str
    bank_name: str
    
    # Protocol configuration
    supported_protocols: List[BankingProtocol]
    preferred_protocol: BankingProtocol
    
    # Connection details
    sftp_host: Optional[str] = None
    sftp_port: int = 22
    sftp_username: Optional[str] = None
    sftp_key_path: Optional[str] = None
    sftp_directory: str = "/incoming"
    
    # API configuration
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_cert_path: Optional[str] = None
    
    # Format specifications
    file_format: str = "xml"
    encoding: str = "utf-8"
    line_ending: str = "CRLF"
    
    # Business rules
    batch_size_limit: int = 1000
    daily_limit_usd: Decimal = Decimal("10000000")  # $10M default
    cut_off_time: str = "15:00"  # 3 PM EST
    
    # Reconciliation
    statement_schedule: str = "daily"  # daily, weekly, monthly
    statement_format: BankingProtocol = BankingProtocol.BAI2
    
    # Status
    is_active: bool = True
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['supported_protocols'] = [p.value for p in self.supported_protocols]
        data['preferred_protocol'] = self.preferred_protocol.value
        data['statement_format'] = self.statement_format.value
        data['daily_limit_usd'] = str(self.daily_limit_usd)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class EnterprisePayment:
    """Enterprise payment instruction."""
    payment_id: str
    
    # Payment details
    amount_usd: Decimal
    currency: str = "USD"
    payment_date: datetime = None
    
    # Counterparty details
    payee_name: str = ""
    payee_account: str = ""
    payee_routing: str = ""
    payee_bank_name: str = ""
    payee_address: Optional[str] = None
    
    # Payer details
    payer_name: str = ""
    payer_account: str = ""
    payer_routing: str = ""
    
    # Payment metadata
    description: str = ""
    reference_number: str = ""
    internal_id: str = ""
    
    # Processing details
    bank_profile_id: str = ""
    protocol: BankingProtocol = BankingProtocol.ACH_NACHA
    transfer_method: TransferMethod = TransferMethod.SFTP
    
    # Status tracking
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Reconciliation
    bank_reference: Optional[str] = None
    trace_number: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.payment_date is None:
            self.payment_date = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['amount_usd'] = str(self.amount_usd)
        data['protocol'] = self.protocol.value
        data['transfer_method'] = self.transfer_method.value
        data['status'] = self.status.value
        data['payment_date'] = self.payment_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['submitted_at'] = self.submitted_at.isoformat() if self.submitted_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


@dataclass
class PaymentBatch:
    """Batch of payments for processing."""
    batch_id: str
    bank_profile_id: str
    
    # Batch details
    payments: List[EnterprisePayment]
    total_amount_usd: Decimal
    payment_count: int
    
    # Processing
    protocol: BankingProtocol
    transfer_method: TransferMethod
    
    # Status
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = None
    submitted_at: Optional[datetime] = None
    
    # File details
    output_filename: Optional[str] = None
    file_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        
        # Calculate totals
        self.payment_count = len(self.payments)
        self.total_amount_usd = sum(p.amount_usd for p in self.payments)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['total_amount_usd'] = str(self.total_amount_usd)
        data['protocol'] = self.protocol.value
        data['transfer_method'] = self.transfer_method.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['submitted_at'] = self.submitted_at.isoformat() if self.submitted_at else None
        data['payments'] = [p.to_dict() for p in self.payments]
        return data


class BankingProtocolFormatter:
    """Formats payments according to banking protocols."""
    
    @staticmethod
    def format_ach_nacha(batch: PaymentBatch, bank_profile: BankProfile) -> str:
        """Format as ACH NACHA file."""
        lines = []
        
        # File Header Record (1)
        now = datetime.now()
        file_header = (
            "1" +  # Record Type
            "01" +  # Priority Code
            " " * 10 +  # Immediate Destination (bank routing)
            " " * 10 +  # Immediate Origin (company ID)
            now.strftime("%y%m%d") +  # File Creation Date
            now.strftime("%H%M") +    # File Creation Time
            "A" +  # File ID Modifier
            "094" +  # Record Size
            "10" +   # Blocking Factor
            "1" +    # Format Code
            f"{'ODIN BRIDGE PRO':<23}" +  # Destination Name
            f"{'ODIN PAYMENTS':<23}" +    # Origin Name
            " " * 8  # Reference Code
        )
        lines.append(file_header)
        
        # Batch Header Record (5)
        batch_header = (
            "5" +  # Record Type
            "200" +  # Service Class Code (Credits/Debits)
            f"{'ODIN PAY':<16}" +  # Company Name
            " " * 20 +  # Company Discretionary Data
            "1234567890" +  # Company ID
            "PPD" +  # Standard Entry Class
            f"{'PAYMENT':<10}" +  # Entry Description
            now.strftime("%y%m%d") +  # Company Descriptive Date
            now.strftime("%y%m%d") +  # Effective Entry Date
            " " * 3 +  # Settlement Date
            "1" +  # Originator Status Code
            bank_profile.sftp_directory[:8].ljust(8) +  # Originating DFI
            f"{1:07d}"  # Batch Number
        )
        lines.append(batch_header)
        
        # Entry Detail Records (6)
        for i, payment in enumerate(batch.payments):
            entry_detail = (
                "6" +  # Record Type
                "22" +  # Transaction Code (Checking Credit)
                payment.payee_routing[:9].ljust(9) +  # Receiving DFI
                payment.payee_account[-17:].ljust(17) +  # DFI Account Number
                f"{int(payment.amount_usd * 100):010d}" +  # Amount (cents)
                payment.reference_number[-15:].ljust(15) +  # Individual ID
                payment.payee_name[:22].ljust(22) +  # Individual Name
                " " * 2 +  # Discretionary Data
                "0" +  # Addenda Record Indicator
                f"{(i + 1):07d}"  # Trace Number
            )
            lines.append(entry_detail)
        
        # Batch Control Record (8)
        total_credits = sum(p.amount_usd for p in batch.payments)
        batch_control = (
            "8" +  # Record Type
            "200" +  # Service Class Code
            f"{len(batch.payments):06d}" +  # Entry/Addenda Count
            "000000000000000000000000" +  # Entry Hash (would calculate real)
            f"{int(total_credits * 100):012d}" +  # Total Credit Amount
            "000000000000" +  # Total Debit Amount
            "1234567890" +  # Company ID
            " " * 19 +  # Message Authentication Code
            " " * 6 +  # Reserved
            bank_profile.sftp_directory[:8].ljust(8) +  # Originating DFI
            f"{1:07d}"  # Batch Number
        )
        lines.append(batch_control)
        
        # File Control Record (9)
        file_control = (
            "9" +  # Record Type
            f"{1:06d}" +  # Batch Count
            f"{1:06d}" +  # Block Count
            f"{len(batch.payments):08d}" +  # Entry/Addenda Count
            "000000000000000000000000" +  # Entry Hash
            f"{int(total_credits * 100):012d}" +  # Total Credits
            "000000000000" +  # Total Debits
            " " * 39  # Reserved
        )
        lines.append(file_control)
        
        # Pad to block boundary
        while len(lines) % 10 != 0:
            lines.append("9" * 94)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_iso20022_pain001(batch: PaymentBatch, bank_profile: BankProfile) -> str:
        """Format as ISO 20022 PAIN.001 XML."""
        root = ET.Element("Document")
        root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
        
        # Customer Credit Transfer Initiation
        cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")
        
        # Group Header
        grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = batch.batch_id
        ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now().isoformat()
        ET.SubElement(grp_hdr, "NbOfTxs").text = str(len(batch.payments))
        ET.SubElement(grp_hdr, "CtrlSum").text = str(batch.total_amount_usd)
        
        # Initiating Party
        initg_pty = ET.SubElement(grp_hdr, "InitgPty")
        ET.SubElement(initg_pty, "Nm").text = "ODIN Bridge Pro"
        
        # Payment Information
        pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
        ET.SubElement(pmt_inf, "PmtInfId").text = f"BATCH_{batch.batch_id}"
        ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"  # Transfer
        ET.SubElement(pmt_inf, "NbOfTxs").text = str(len(batch.payments))
        ET.SubElement(pmt_inf, "CtrlSum").text = str(batch.total_amount_usd)
        
        # Requested Execution Date
        ET.SubElement(pmt_inf, "ReqdExctnDt").text = datetime.now().strftime("%Y-%m-%d")
        
        # Debtor (Payer)
        dbtr = ET.SubElement(pmt_inf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = batch.payments[0].payer_name if batch.payments else "ODIN"
        
        # Debtor Account
        dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
        ET.SubElement(dbtr_acct, "Id").text = batch.payments[0].payer_account if batch.payments else ""
        
        # Credit Transfer Transaction Information
        for payment in batch.payments:
            cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
            
            # Payment ID
            pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
            ET.SubElement(pmt_id, "EndToEndId").text = payment.payment_id
            
            # Amount
            amt = ET.SubElement(cdt_trf_tx_inf, "Amt")
            instd_amt = ET.SubElement(amt, "InstdAmt")
            instd_amt.set("Ccy", payment.currency)
            instd_amt.text = str(payment.amount_usd)
            
            # Creditor (Payee)
            cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
            ET.SubElement(cdtr, "Nm").text = payment.payee_name
            
            # Creditor Account
            cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
            ET.SubElement(cdtr_acct, "Id").text = payment.payee_account
            
            # Remittance Information
            if payment.description:
                rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
                ET.SubElement(rmt_inf, "Ustrd").text = payment.description
        
        return ET.tostring(root, encoding='unicode', xml_declaration=True)
    
    @staticmethod
    def format_csv_custom(batch: PaymentBatch, bank_profile: BankProfile) -> str:
        """Format as custom CSV."""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header row
        writer.writerow([
            "Payment_ID", "Amount", "Currency", "Payee_Name", 
            "Payee_Account", "Payee_Routing", "Description", 
            "Reference", "Payment_Date"
        ])
        
        # Payment rows
        for payment in batch.payments:
            writer.writerow([
                payment.payment_id,
                str(payment.amount_usd),
                payment.currency,
                payment.payee_name,
                payment.payee_account,
                payment.payee_routing,
                payment.description,
                payment.reference_number,
                payment.payment_date.strftime("%Y-%m-%d")
            ])
        
        return output.getvalue()


class SFTPConnector:
    """SFTP connection management for bank file transfers."""
    
    def __init__(self, bank_profile: BankProfile):
        self.bank_profile = bank_profile
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
    
    async def connect(self) -> bool:
        """Connect to bank SFTP server."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key if specified
            private_key = None
            if self.bank_profile.sftp_key_path:
                private_key = paramiko.RSAKey.from_private_key_file(
                    self.bank_profile.sftp_key_path
                )
            
            # Connect
            self.client.connect(
                hostname=self.bank_profile.sftp_host,
                port=self.bank_profile.sftp_port,
                username=self.bank_profile.sftp_username,
                pkey=private_key,
                timeout=30
            )
            
            # Open SFTP session
            self.sftp = self.client.open_sftp()
            
            print(f"🔗 Connected to {self.bank_profile.bank_name} SFTP")
            return True
            
        except Exception as e:
            print(f"❌ SFTP connection failed: {e}")
            return False
    
    async def upload_file(self, local_path: str, remote_filename: str) -> bool:
        """Upload file to bank SFTP server."""
        try:
            if not self.sftp:
                await self.connect()
            
            remote_path = f"{self.bank_profile.sftp_directory}/{remote_filename}"
            
            # Upload file
            self.sftp.put(local_path, remote_path)
            
            print(f"📤 Uploaded {remote_filename} to {self.bank_profile.bank_name}")
            return True
            
        except Exception as e:
            print(f"❌ File upload failed: {e}")
            return False
    
    async def download_file(self, remote_filename: str, local_path: str) -> bool:
        """Download file from bank SFTP server."""
        try:
            if not self.sftp:
                await self.connect()
            
            remote_path = f"{self.bank_profile.sftp_directory}/{remote_filename}"
            
            # Download file
            self.sftp.get(remote_path, local_path)
            
            print(f"📥 Downloaded {remote_filename} from {self.bank_profile.bank_name}")
            return True
            
        except Exception as e:
            print(f"❌ File download failed: {e}")
            return False
    
    async def list_files(self, directory: Optional[str] = None) -> List[str]:
        """List files in directory."""
        try:
            if not self.sftp:
                await self.connect()
            
            list_dir = directory or self.bank_profile.sftp_directory
            files = self.sftp.listdir(list_dir)
            
            return files
            
        except Exception as e:
            print(f"❌ Directory listing failed: {e}")
            return []
    
    def disconnect(self):
        """Disconnect from SFTP server."""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
        except Exception:
            pass


class PaymentsBridgeProStorage:
    """Storage backend for Payments Bridge Pro."""
    
    def __init__(self, storage_path: str = "data/payments"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    # Bank Profile Storage
    async def store_bank_profile(self, profile: BankProfile) -> bool:
        """Store bank profile."""
        try:
            profile_file = self.storage_path / "banks" / f"{profile.bank_id}.json"
            profile_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(profile_file, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store bank profile: {e}")
            return False
    
    async def get_bank_profile(self, bank_id: str) -> Optional[BankProfile]:
        """Get bank profile."""
        try:
            profile_file = self.storage_path / "banks" / f"{bank_id}.json"
            if profile_file.exists():
                with open(profile_file, 'r') as f:
                    data = json.load(f)
                return BankProfile(**data)
        except Exception as e:
            print(f"Failed to get bank profile: {e}")
        return None
    
    # Payment Storage
    async def store_payment(self, payment: EnterprisePayment) -> bool:
        """Store payment."""
        try:
            payment_file = self.storage_path / "payments" / f"{payment.payment_id}.json"
            payment_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(payment_file, 'w') as f:
                json.dump(payment.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store payment: {e}")
            return False
    
    async def get_payment(self, payment_id: str) -> Optional[EnterprisePayment]:
        """Get payment."""
        try:
            payment_file = self.storage_path / "payments" / f"{payment_id}.json"
            if payment_file.exists():
                with open(payment_file, 'r') as f:
                    data = json.load(f)
                return EnterprisePayment(**data)
        except Exception as e:
            print(f"Failed to get payment: {e}")
        return None
    
    # Batch Storage
    async def store_batch(self, batch: PaymentBatch) -> bool:
        """Store payment batch."""
        try:
            batch_file = self.storage_path / "batches" / f"{batch.batch_id}.json"
            batch_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(batch_file, 'w') as f:
                json.dump(batch.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store batch: {e}")
            return False


class PaymentsBridgeProService:
    """Main Payments Bridge Pro service."""
    
    def __init__(self, storage: Optional[PaymentsBridgeProStorage] = None):
        self.storage = storage or PaymentsBridgeProStorage()
        self.formatter = BankingProtocolFormatter()
        
        # Background tasks
        self._processing_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start Payments Bridge Pro service."""
        print("💳 Starting Payments Bridge Pro Service")
        
        # Start batch processing task
        self._processing_task = asyncio.create_task(self._batch_processor())
        
        print("✅ Payments Bridge Pro started")
    
    async def stop(self):
        """Stop service."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        print("✅ Payments Bridge Pro stopped")
    
    async def create_enterprise_payment(self, amount_usd: Decimal, payee_name: str,
                                      payee_account: str, payee_routing: str,
                                      description: str, bank_profile_id: str,
                                      **kwargs) -> EnterprisePayment:
        """Create enterprise payment."""
        payment = EnterprisePayment(
            payment_id=str(uuid.uuid4()),
            amount_usd=amount_usd,
            payee_name=payee_name,
            payee_account=payee_account,
            payee_routing=payee_routing,
            description=description,
            bank_profile_id=bank_profile_id,
            reference_number=kwargs.get('reference_number', str(uuid.uuid4())[:8]),
            payer_name=kwargs.get('payer_name', 'ODIN Client'),
            payer_account=kwargs.get('payer_account', ''),
            payer_routing=kwargs.get('payer_routing', ''),
            protocol=kwargs.get('protocol', BankingProtocol.ACH_NACHA)
        )
        
        await self.storage.store_payment(payment)
        return payment
    
    async def process_payment_batch(self, payments: List[EnterprisePayment],
                                  bank_profile_id: str) -> PaymentBatch:
        """Process batch of payments."""
        try:
            # Get bank profile
            bank_profile = await self.storage.get_bank_profile(bank_profile_id)
            if not bank_profile:
                raise ValueError(f"Bank profile {bank_profile_id} not found")
            
            # Create batch
            batch = PaymentBatch(
                batch_id=str(uuid.uuid4()),
                bank_profile_id=bank_profile_id,
                payments=payments,
                protocol=bank_profile.preferred_protocol,
                transfer_method=TransferMethod.SFTP,
                total_amount_usd=sum(p.amount_usd for p in payments),
                payment_count=len(payments)
            )
            
            # Generate payment file
            if batch.protocol == BankingProtocol.ACH_NACHA:
                file_content = self.formatter.format_ach_nacha(batch, bank_profile)
                file_extension = ".ach"
            elif batch.protocol == BankingProtocol.ISO20022_PAIN001:
                file_content = self.formatter.format_iso20022_pain001(batch, bank_profile)
                file_extension = ".xml"
            else:
                file_content = self.formatter.format_csv_custom(batch, bank_profile)
                file_extension = ".csv"
            
            # Save file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ODIN_BATCH_{batch.batch_id[:8]}_{timestamp}{file_extension}"
            
            output_dir = Path("data/payments/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            file_path = output_dir / filename
            
            with open(file_path, 'w', encoding=bank_profile.encoding) as f:
                f.write(file_content)
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_content.encode()).hexdigest()
            
            batch.output_filename = filename
            batch.file_hash = file_hash
            batch.status = PaymentStatus.SUBMITTED
            batch.submitted_at = datetime.now(timezone.utc)
            
            # Upload to bank if SFTP enabled
            if bank_profile.sftp_host:
                connector = SFTPConnector(bank_profile)
                success = await connector.upload_file(str(file_path), filename)
                
                if success:
                    batch.status = PaymentStatus.PROCESSING
                else:
                    batch.status = PaymentStatus.FAILED
                
                connector.disconnect()
            
            # Update payment statuses
            for payment in payments:
                payment.status = batch.status
                payment.submitted_at = batch.submitted_at
                await self.storage.store_payment(payment)
            
            # Store batch
            await self.storage.store_batch(batch)
            
            print(f"💳 Processed batch {batch.batch_id} with {len(payments)} payments (${batch.total_amount_usd})")
            
            return batch
            
        except Exception as e:
            print(f"❌ Batch processing failed: {e}")
            raise
    
    async def get_payment_stats(self) -> Dict[str, Any]:
        """Get payment statistics."""
        try:
            # This would need more sophisticated querying in production
            return {
                "status": "operational",
                "active_banks": 0,  # Would count from storage
                "pending_payments": 0,
                "monthly_volume_usd": "0",
                "last_batch_processed": None
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _batch_processor(self):
        """Background batch processing."""
        while True:
            try:
                # Check for pending payments to batch
                # This would implement sophisticated batching logic
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Batch processor error: {e}")
                await asyncio.sleep(3600)  # Sleep 1 hour on error


# Global service
_payments_service: Optional[PaymentsBridgeProService] = None


async def get_payments_service() -> PaymentsBridgeProService:
    """Get global payments service."""
    global _payments_service
    if not _payments_service:
        _payments_service = PaymentsBridgeProService()
        await _payments_service.start()
    return _payments_service


# Health check
async def payments_health_check() -> Dict[str, Any]:
    """Check payments service health."""
    try:
        payments = await get_payments_service()
        stats = await payments.get_payment_stats()
        
        return {
            "status": "healthy" if stats.get("status") == "operational" else "degraded",
            "message": "Payments Bridge Pro operational",
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Payments health check failed: {e}",
            "stats": {}
        }
