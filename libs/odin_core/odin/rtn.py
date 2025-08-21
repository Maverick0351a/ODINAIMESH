"""
ODIN Receipts Transparency Network (RTN)

A neutral, append-only transparency log for ODIN receipts (hashes only),
like Certificate Transparency but for AI traffic. Creates verifiable public
good where customers can prove "we did what we said" without revealing payloads.

This becomes the de facto standard that creates ODIN's network effect moat.
"""

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import base64
from enum import Enum

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class RTNEntryType(Enum):
    """Types of entries in the RTN log."""
    RECEIPT = "receipt"
    DAY_ROOT = "day_root"
    ANCHOR = "anchor"


@dataclass
class RTNEntry:
    """Entry in the ODIN Receipts Transparency Network."""
    trace_id: str
    receipt_cid: str
    receipt_hash: str  # SHA256 of receipt content
    timestamp: datetime
    realm: str
    service: str
    entry_type: RTNEntryType = RTNEntryType.RECEIPT
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['entry_type'] = self.entry_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RTNEntry':
        """Create from dictionary."""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['entry_type'] = RTNEntryType(data['entry_type'])
        return cls(**data)


@dataclass
class MerkleNode:
    """Node in Merkle tree for RTN."""
    hash: str
    left_child: Optional['MerkleNode'] = None
    right_child: Optional['MerkleNode'] = None
    data: Optional[RTNEntry] = None
    
    @property
    def is_leaf(self) -> bool:
        return self.left_child is None and self.right_child is None


@dataclass
class MerkleProof:
    """Merkle inclusion proof for RTN entry."""
    entry_hash: str
    root_hash: str
    proof_path: List[Tuple[str, str]]  # (hash, position: 'left'|'right')
    tree_size: int
    day_date: str
    
    def verify(self) -> bool:
        """Verify the Merkle proof."""
        current_hash = self.entry_hash
        
        for proof_hash, position in self.proof_path:
            if position == 'left':
                current_hash = self._hash_pair(proof_hash, current_hash)
            else:
                current_hash = self._hash_pair(current_hash, proof_hash)
                
        return current_hash == self.root_hash
    
    @staticmethod
    def _hash_pair(left: str, right: str) -> str:
        """Hash two strings together for Merkle tree."""
        combined = left + right
        return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class DayRoot:
    """Daily Merkle tree root with signature."""
    date: str  # YYYY-MM-DD
    root_hash: str
    tree_size: int
    timestamp: datetime
    signature: str
    public_key: str
    anchor_hash: Optional[str] = None  # Optional blockchain anchor
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class RTNStorage:
    """Storage backend for RTN data."""
    
    def __init__(self, storage_path: str = "data/rtn"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
    async def store_entry(self, entry: RTNEntry) -> bool:
        """Store RTN entry."""
        try:
            date_str = entry.timestamp.strftime("%Y-%m-%d")
            day_file = self.storage_path / f"entries_{date_str}.jsonl"
            
            with open(day_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')
            return True
        except Exception as e:
            print(f"Failed to store RTN entry: {e}")
            return False
            
    async def get_entries_for_day(self, date: str) -> List[RTNEntry]:
        """Get all entries for a specific day."""
        day_file = self.storage_path / f"entries_{date}.jsonl"
        entries = []
        
        if day_file.exists():
            with open(day_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entry_data = json.loads(line)
                        entries.append(RTNEntry.from_dict(entry_data))
        
        return entries
    
    async def store_day_root(self, day_root: DayRoot) -> bool:
        """Store daily root hash."""
        try:
            root_file = self.storage_path / f"root_{day_root.date}.json"
            with open(root_file, 'w') as f:
                json.dump(day_root.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to store day root: {e}")
            return False
            
    async def get_day_root(self, date: str) -> Optional[DayRoot]:
        """Get day root for specific date."""
        root_file = self.storage_path / f"root_{date}.json"
        
        if root_file.exists():
            with open(root_file, 'r') as f:
                data = json.load(f)
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                return DayRoot(**data)
        return None


class MerkleTreeBuilder:
    """Builds Merkle trees for daily RTN entries."""
    
    @staticmethod
    def build_tree(entries: List[RTNEntry]) -> MerkleNode:
        """Build Merkle tree from entries."""
        if not entries:
            # Empty tree
            empty_hash = hashlib.sha256(b"").hexdigest()
            return MerkleNode(hash=empty_hash)
        
        # Create leaf nodes
        leaf_nodes = []
        for entry in entries:
            entry_hash = hashlib.sha256(
                json.dumps(entry.to_dict(), sort_keys=True).encode()
            ).hexdigest()
            leaf_nodes.append(MerkleNode(hash=entry_hash, data=entry))
        
        # Build tree bottom-up
        current_level = leaf_nodes
        
        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                combined_hash = MerkleTreeBuilder._hash_nodes(left, right)
                parent = MerkleNode(
                    hash=combined_hash,
                    left_child=left,
                    right_child=right if right != left else None
                )
                next_level.append(parent)
            
            current_level = next_level
        
        return current_level[0]
    
    @staticmethod
    def generate_proof(tree_root: MerkleNode, target_entry: RTNEntry) -> Optional[MerkleProof]:
        """Generate inclusion proof for an entry."""
        target_hash = hashlib.sha256(
            json.dumps(target_entry.to_dict(), sort_keys=True).encode()
        ).hexdigest()
        
        proof_path = []
        tree_size = MerkleTreeBuilder._count_leaves(tree_root)
        
        if MerkleTreeBuilder._find_proof_path(tree_root, target_hash, proof_path):
            return MerkleProof(
                entry_hash=target_hash,
                root_hash=tree_root.hash,
                proof_path=proof_path,
                tree_size=tree_size,
                day_date=target_entry.timestamp.strftime("%Y-%m-%d")
            )
        
        return None
    
    @staticmethod
    def _hash_nodes(left: MerkleNode, right: MerkleNode) -> str:
        """Hash two nodes together."""
        combined = left.hash + right.hash
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def _count_leaves(node: MerkleNode) -> int:
        """Count leaf nodes in tree."""
        if node.is_leaf:
            return 1
        
        count = 0
        if node.left_child:
            count += MerkleTreeBuilder._count_leaves(node.left_child)
        if node.right_child:
            count += MerkleTreeBuilder._count_leaves(node.right_child)
        
        return count
    
    @staticmethod
    def _find_proof_path(node: MerkleNode, target_hash: str, proof_path: List[Tuple[str, str]]) -> bool:
        """Find proof path to target hash."""
        if node.is_leaf:
            return node.hash == target_hash
        
        # Check left subtree
        if node.left_child and MerkleTreeBuilder._find_proof_path(node.left_child, target_hash, proof_path):
            if node.right_child:
                proof_path.append((node.right_child.hash, 'right'))
            return True
        
        # Check right subtree
        if node.right_child and MerkleTreeBuilder._find_proof_path(node.right_child, target_hash, proof_path):
            if node.left_child:
                proof_path.append((node.left_child.hash, 'left'))
            return True
        
        return False


class RTNSigner:
    """Handles cryptographic signing for RTN."""
    
    def __init__(self, private_key_path: Optional[str] = None):
        self.private_key_path = private_key_path or os.getenv("RTN_PRIVATE_KEY_PATH")
        self.private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self.public_key: Optional[ed25519.Ed25519PublicKey] = None
        self._load_or_generate_keys()
    
    def _load_or_generate_keys(self):
        """Load existing keys or generate new ones."""
        if not CRYPTO_AVAILABLE:
            print("Warning: Cryptography not available, signatures disabled")
            return
            
        if self.private_key_path and os.path.exists(self.private_key_path):
            # Load existing key
            with open(self.private_key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
        else:
            # Generate new key
            self.private_key = ed25519.Ed25519PrivateKey.generate()
            
            if self.private_key_path:
                # Save key
                os.makedirs(os.path.dirname(self.private_key_path), exist_ok=True)
                with open(self.private_key_path, 'wb') as f:
                    f.write(self.private_key.private_bytes(
                        encoding=Encoding.PEM,
                        format=PrivateFormat.PKCS8,
                        encryption_algorithm=NoEncryption()
                    ))
        
        self.public_key = self.private_key.public_key()
    
    def sign_day_root(self, root_hash: str, date: str, tree_size: int) -> Tuple[str, str]:
        """Sign a day root hash."""
        if not self.private_key:
            return "unsigned", "no_key"
        
        # Create canonical message to sign
        message_data = {
            "root_hash": root_hash,
            "date": date,
            "tree_size": tree_size,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        message = json.dumps(message_data, sort_keys=True).encode()
        
        # Sign
        signature = self.private_key.sign(message)
        signature_b64 = base64.b64encode(signature).decode()
        
        # Get public key
        public_key_bytes = self.public_key.public_bytes(
            encoding=Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        public_key_b64 = base64.b64encode(public_key_bytes).decode()
        
        return signature_b64, public_key_b64
    
    def verify_signature(self, signature_b64: str, public_key_b64: str, 
                        root_hash: str, date: str, tree_size: int, timestamp: str) -> bool:
        """Verify a day root signature."""
        if not CRYPTO_AVAILABLE:
            return False
            
        try:
            # Reconstruct message
            message_data = {
                "root_hash": root_hash,
                "date": date,
                "tree_size": tree_size,
                "timestamp": timestamp
            }
            message = json.dumps(message_data, sort_keys=True).encode()
            
            # Decode signature and public key
            signature = base64.b64decode(signature_b64)
            public_key_bytes = base64.b64decode(public_key_b64)
            
            # Verify
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, message)
            return True
            
        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False


class RTNService:
    """Main RTN service managing the transparency network."""
    
    def __init__(self, storage: Optional[RTNStorage] = None, 
                 signer: Optional[RTNSigner] = None):
        self.storage = storage or RTNStorage()
        self.signer = signer or RTNSigner()
        self.tree_builder = MerkleTreeBuilder()
        
        # Configuration
        self.inclusion_required_realms = set(os.getenv("RTN_REQUIRED_REALMS", "").split(","))
        self.daily_root_hour = int(os.getenv("RTN_DAILY_ROOT_HOUR", "23"))  # UTC hour to generate daily roots
        
        # Start background tasks
        self._daily_root_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start RTN service."""
        print("🌐 Starting ODIN Receipts Transparency Network (RTN)")
        
        # Start daily root generation task
        self._daily_root_task = asyncio.create_task(self._daily_root_generator())
        
        print("✅ RTN service started")
    
    async def stop(self):
        """Stop RTN service."""
        if self._daily_root_task:
            self._daily_root_task.cancel()
            try:
                await self._daily_root_task
            except asyncio.CancelledError:
                pass
        
        print("✅ RTN service stopped")
    
    async def submit_receipt(self, trace_id: str, receipt_cid: str, 
                           receipt_content: str, realm: str, service: str) -> bool:
        """Submit receipt to transparency network."""
        try:
            # Calculate receipt hash
            receipt_hash = hashlib.sha256(receipt_content.encode()).hexdigest()
            
            # Create RTN entry
            entry = RTNEntry(
                trace_id=trace_id,
                receipt_cid=receipt_cid,
                receipt_hash=receipt_hash,
                timestamp=datetime.now(timezone.utc),
                realm=realm,
                service=service,
                metadata={"content_length": len(receipt_content)}
            )
            
            # Store entry
            success = await self.storage.store_entry(entry)
            
            if success:
                print(f"📝 RTN entry submitted: {trace_id} -> {receipt_hash[:16]}")
            
            return success
            
        except Exception as e:
            print(f"Failed to submit RTN entry: {e}")
            return False
    
    async def get_inclusion_proof(self, receipt_hash: str) -> Optional[Dict[str, Any]]:
        """Get inclusion proof for a receipt."""
        try:
            # Find the entry across all days (in practice, we'd optimize this)
            for days_back in range(30):  # Search last 30 days
                search_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
                entries = await self.storage.get_entries_for_day(search_date)
                
                # Find matching entry
                target_entry = None
                for entry in entries:
                    if entry.receipt_hash == receipt_hash:
                        target_entry = entry
                        break
                
                if target_entry:
                    # Build tree for that day
                    tree_root = self.tree_builder.build_tree(entries)
                    
                    # Generate proof
                    proof = self.tree_builder.generate_proof(tree_root, target_entry)
                    
                    if proof:
                        # Get day root signature
                        day_root = await self.storage.get_day_root(search_date)
                        
                        return {
                            "receipt_hash": receipt_hash,
                            "proof": {
                                "entry_hash": proof.entry_hash,
                                "root_hash": proof.root_hash,
                                "proof_path": proof.proof_path,
                                "tree_size": proof.tree_size,
                                "day_date": proof.day_date
                            },
                            "day_root": day_root.to_dict() if day_root else None,
                            "verified": proof.verify(),
                            "entry": target_entry.to_dict()
                        }
            
            return None
            
        except Exception as e:
            print(f"Failed to get inclusion proof: {e}")
            return None
    
    async def check_inclusion_required(self, realm: str) -> bool:
        """Check if RTN inclusion is required for this realm."""
        return realm in self.inclusion_required_realms
    
    async def get_daily_root(self, date: str) -> Optional[Dict[str, Any]]:
        """Get daily root for specific date."""
        day_root = await self.storage.get_day_root(date)
        return day_root.to_dict() if day_root else None
    
    async def _daily_root_generator(self):
        """Background task to generate daily roots."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                
                # Check if it's time to generate daily root
                if now.hour == self.daily_root_hour and now.minute < 5:
                    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    # Check if we already have a root for yesterday
                    existing_root = await self.storage.get_day_root(yesterday)
                    if not existing_root:
                        await self._generate_daily_root(yesterday)
                
                # Sleep until next check (5 minutes)
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Daily root generator error: {e}")
                await asyncio.sleep(60)
    
    async def _generate_daily_root(self, date: str):
        """Generate and sign daily root for a specific date."""
        try:
            print(f"🌳 Generating daily root for {date}")
            
            # Get all entries for the day
            entries = await self.storage.get_entries_for_day(date)
            
            # Build Merkle tree
            tree_root = self.tree_builder.build_tree(entries)
            
            # Sign the root
            signature, public_key = self.signer.sign_day_root(
                tree_root.hash, date, len(entries)
            )
            
            # Create day root record
            day_root = DayRoot(
                date=date,
                root_hash=tree_root.hash,
                tree_size=len(entries),
                timestamp=datetime.now(timezone.utc),
                signature=signature,
                public_key=public_key
            )
            
            # Store day root
            await self.storage.store_day_root(day_root)
            
            print(f"✅ Daily root generated for {date}: {tree_root.hash[:16]} ({len(entries)} entries)")
            
            # TODO: Optional blockchain anchoring
            await self._anchor_to_blockchain(day_root)
            
        except Exception as e:
            print(f"Failed to generate daily root for {date}: {e}")
    
    async def _anchor_to_blockchain(self, day_root: DayRoot):
        """Optional: Anchor daily root to blockchain."""
        # This would integrate with a blockchain service
        # For MVP, we'll just log the intent
        print(f"📦 Would anchor to blockchain: {day_root.root_hash}")
        
        # In production, this would:
        # 1. Submit to a blockchain (Ethereum, Polygon, etc.)
        # 2. Wait for confirmation
        # 3. Update day_root with anchor_hash
        # 4. Store updated day_root
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get RTN statistics."""
        try:
            # Count entries for last 7 days
            total_entries = 0
            daily_counts = {}
            
            for days_back in range(7):
                date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
                entries = await self.storage.get_entries_for_day(date)
                count = len(entries)
                total_entries += count
                daily_counts[date] = count
            
            return {
                "total_entries_7d": total_entries,
                "daily_counts": daily_counts,
                "inclusion_required_realms": list(self.inclusion_required_realms),
                "service_status": "operational"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "service_status": "degraded"
            }


# Global RTN service instance
_rtn_service: Optional[RTNService] = None


async def get_rtn_service() -> RTNService:
    """Get global RTN service instance."""
    global _rtn_service
    if not _rtn_service:
        _rtn_service = RTNService()
        await _rtn_service.start()
    return _rtn_service


async def submit_receipt_to_rtn(trace_id: str, receipt_cid: str, 
                               receipt_content: str, realm: str, service: str) -> bool:
    """Submit receipt to RTN (convenience function)."""
    rtn = await get_rtn_service()
    return await rtn.submit_receipt(trace_id, receipt_cid, receipt_content, realm, service)


async def get_receipt_inclusion_proof(receipt_hash: str) -> Optional[Dict[str, Any]]:
    """Get inclusion proof for receipt (convenience function)."""
    rtn = await get_rtn_service()
    return await rtn.get_inclusion_proof(receipt_hash)


# Health check for RTN
async def rtn_health_check() -> Dict[str, Any]:
    """Check RTN health."""
    try:
        rtn = await get_rtn_service()
        stats = await rtn.get_stats()
        
        return {
            "status": "healthy" if stats.get("service_status") == "operational" else "degraded",
            "message": "RTN operational" if stats.get("service_status") == "operational" else "RTN degraded",
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"RTN health check failed: {e}",
            "stats": {}
        }
