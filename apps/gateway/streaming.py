"""
Merkle-Stream support for 0.9.0-beta

Provides streaming endpoint with Merkle root calculation for receipt chains.
Optional feature that can be enabled via environment configuration.
"""
from __future__ import annotations

import os
import json
import time
import hashlib
from typing import Any, Dict, List, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from libs.odin_core.odin import compute_cid


@dataclass
class StreamChunk:
    """Individual chunk in a Merkle stream."""
    sequence: int
    data: Dict[str, Any]
    timestamp: int
    hash: str  # Hash of this chunk
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sequence": self.sequence,
            "data": self.data,
            "timestamp": self.timestamp,
            "hash": self.hash,
        }


class StreamRequest(BaseModel):
    """Request to start a Merkle stream."""
    payload: Dict[str, Any]
    chunk_size: Optional[int] = 1024  # Max items per chunk
    include_merkle: bool = True  # Include Merkle root in headers


class MerkleStreamProcessor:
    """
    Processes streaming data and computes Merkle roots for receipt verification.
    
    Features:
    - Streams data in configurable chunks
    - Computes hash for each chunk
    - Calculates Merkle root for entire stream
    - Generates receipt with stream metadata
    """
    
    def __init__(self, chunk_size: int = 1024):
        self.chunk_size = chunk_size
        self.chunks: List[StreamChunk] = []
        self.start_time = int(time.time() * 1000)
    
    def add_chunk(self, sequence: int, data: Dict[str, Any]) -> StreamChunk:
        """Add a chunk to the stream and compute its hash."""
        timestamp = int(time.time() * 1000)
        
        # Serialize chunk data deterministically
        chunk_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
        chunk_bytes = chunk_json.encode('utf-8')
        
        # Compute chunk hash
        chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()
        
        chunk = StreamChunk(
            sequence=sequence,
            data=data,
            timestamp=timestamp,
            hash=chunk_hash,
        )
        
        self.chunks.append(chunk)
        return chunk
    
    def compute_merkle_root(self) -> str:
        """
        Compute Merkle root hash for all chunks in the stream.
        
        Returns:
            Hex-encoded Merkle root hash
        """
        if not self.chunks:
            return hashlib.sha256(b"").hexdigest()
        
        # Start with chunk hashes
        hashes = [chunk.hash for chunk in self.chunks]
        
        # Build Merkle tree bottom-up
        while len(hashes) > 1:
            next_level = []
            for i in range(0, len(hashes), 2):
                left = hashes[i]
                right = hashes[i + 1] if i + 1 < len(hashes) else left
                combined = (left + right).encode('utf-8')
                parent_hash = hashlib.sha256(combined).hexdigest()
                next_level.append(parent_hash)
            hashes = next_level
        
        return hashes[0]
    
    def generate_receipt(self, trace_id: str, stream_id: str) -> Dict[str, Any]:
        """Generate stream receipt with Merkle root and metadata."""
        merkle_root = self.compute_merkle_root()
        end_time = int(time.time() * 1000)
        
        return {
            "type": "odin.stream.receipt",
            "stream_id": stream_id,
            "trace_id": trace_id,
            "merkle_root": merkle_root,
            "chunk_count": len(self.chunks),
            "start_ts": self.start_time,
            "end_ts": end_time,
            "duration_ms": end_time - self.start_time,
            "chunks": [
                {
                    "sequence": chunk.sequence,
                    "hash": chunk.hash,
                    "timestamp": chunk.timestamp,
                }
                for chunk in self.chunks
            ],
        }


# Router for streaming endpoints
stream_router = APIRouter()


@stream_router.post("/v1/mesh/stream")
async def mesh_stream(
    request: StreamRequest,
    req: Request,
) -> StreamingResponse:
    """
    Stream processing endpoint with Merkle root calculation.
    
    Processes payload data in chunks, computes Merkle root for the stream,
    and returns streaming response with X-ODIN-Stream-Root header.
    """
    if not is_streaming_enabled():
        raise HTTPException(
            status_code=501,
            detail="Streaming not enabled. Set ODIN_STREAMING_ENABLED=1"
        )
    
    # Generate stream and trace IDs
    stream_id = f"stream-{int(time.time())}-{os.urandom(4).hex()}"
    trace_id = req.headers.get("X-ODIN-Trace-Id", f"trace-{stream_id}")
    
    # Initialize stream processor
    processor = MerkleStreamProcessor(chunk_size=request.chunk_size or 1024)
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate streaming response with chunks."""
        try:
            # Process payload in chunks
            payload_data = request.payload
            
            # For demo: split payload into chunks based on size
            # In real implementation, this would stream actual data
            if isinstance(payload_data, dict):
                items = list(payload_data.items())
            elif isinstance(payload_data, list):
                items = payload_data
            else:
                items = [payload_data]
            
            chunk_size = request.chunk_size or 1024
            sequence = 0
            
            for i in range(0, len(items), chunk_size):
                chunk_items = items[i:i + chunk_size]
                chunk_data = {
                    "items": chunk_items,
                    "offset": i,
                    "total": len(items),
                }
                
                # Add chunk to processor
                chunk = processor.add_chunk(sequence, chunk_data)
                sequence += 1
                
                # Yield chunk as JSON line
                chunk_json = json.dumps(chunk.to_dict())
                yield f"data: {chunk_json}\n\n"
                
                # Optional delay to simulate streaming
                if os.getenv("ODIN_STREAM_DELAY_MS"):
                    import asyncio
                    delay_ms = int(os.getenv("ODIN_STREAM_DELAY_MS", "0"))
                    if delay_ms > 0:
                        await asyncio.sleep(delay_ms / 1000.0)
            
            # Send final receipt chunk
            receipt = processor.generate_receipt(trace_id, stream_id)
            receipt_json = json.dumps(receipt)
            yield f"data: {receipt_json}\n\n"
            
        except Exception as e:
            error_chunk = {
                "error": str(e),
                "type": "stream.error",
                "timestamp": int(time.time() * 1000),
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    # Compute Merkle root for headers (we need to process once to get this)
    # For a real streaming implementation, this would be computed incrementally
    temp_processor = MerkleStreamProcessor()
    if isinstance(request.payload, dict):
        temp_processor.add_chunk(0, request.payload)
    merkle_root = temp_processor.compute_merkle_root()
    
    # Build response headers
    headers = {
        "X-ODIN-Stream-Id": stream_id,
        "X-ODIN-Trace-Id": trace_id,
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    
    if request.include_merkle:
        headers["X-ODIN-Stream-Root"] = merkle_root
    
    # Record metrics
    try:
        from apps.gateway.metrics import mesh_hops_total
        mesh_hops_total.labels(route="mesh.stream").inc()
    except ImportError:
        pass
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers=headers,
    )


@stream_router.get("/v1/stream/receipt/{stream_id}")
async def get_stream_receipt(stream_id: str) -> Dict[str, Any]:
    """
    Get receipt for a completed stream.
    
    Args:
        stream_id: Stream identifier
    
    Returns:
        Stream receipt with Merkle root and metadata
    """
    # In a real implementation, this would fetch from storage
    # For now, return a placeholder
    return {
        "stream_id": stream_id,
        "status": "completed",
        "message": "Stream receipt lookup not yet implemented",
        "timestamp": int(time.time() * 1000),
    }


def is_streaming_enabled() -> bool:
    """Check if streaming is enabled via environment."""
    return os.getenv("ODIN_STREAMING_ENABLED", "0") != "0"


def get_stream_config() -> Dict[str, Any]:
    """Get streaming configuration from environment."""
    return {
        "enabled": is_streaming_enabled(),
        "default_chunk_size": int(os.getenv("ODIN_STREAM_CHUNK_SIZE", "1024")),
        "max_chunk_size": int(os.getenv("ODIN_STREAM_MAX_CHUNK_SIZE", "10000")),
        "delay_ms": int(os.getenv("ODIN_STREAM_DELAY_MS", "0")),
    }
