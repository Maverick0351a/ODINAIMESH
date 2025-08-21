"""
SBOM (Software Bill of Materials) utilities for 0.9.0-beta

Processes SBOM headers (X-ODIN-Model, X-ODIN-Tool, X-ODIN-Prompt-CID) and 
enhances receipts with software bill of materials information.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from fastapi import Request


class SBOMInfo:
    """Container for SBOM information extracted from headers."""
    
    def __init__(self):
        self.models: List[str] = []
        self.tools: List[str] = []
        self.prompt_cids: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for receipt storage."""
        sbom = {}
        if self.models:
            sbom["models"] = self.models
        if self.tools:
            sbom["tools"] = self.tools
        if self.prompt_cids:
            sbom["prompt_cids"] = self.prompt_cids
        return sbom
    
    def is_empty(self) -> bool:
        """Check if no SBOM information was found."""
        return not (self.models or self.tools or self.prompt_cids)


def extract_sbom_from_headers(headers: Dict[str, str]) -> SBOMInfo:
    """
    Extract SBOM information from request headers.
    
    Headers processed:
    - X-ODIN-Model: AI model identifiers (comma-separated)
    - X-ODIN-Tool: Tool/function identifiers (comma-separated)  
    - X-ODIN-Prompt-CID: Prompt content identifiers (comma-separated)
    
    Args:
        headers: Request headers dictionary
    
    Returns:
        SBOMInfo object with extracted information
    """
    sbom = SBOMInfo()
    
    # Extract models
    model_header = headers.get("X-ODIN-Model") or headers.get("x-odin-model")
    if model_header:
        sbom.models = _parse_csv_header(model_header)
    
    # Extract tools
    tool_header = headers.get("X-ODIN-Tool") or headers.get("x-odin-tool")
    if tool_header:
        sbom.tools = _parse_csv_header(tool_header)
    
    # Extract prompt CIDs
    prompt_header = headers.get("X-ODIN-Prompt-CID") or headers.get("x-odin-prompt-cid")
    if prompt_header:
        sbom.prompt_cids = _parse_csv_header(prompt_header)
    
    return sbom


def extract_sbom_from_request(request: Request) -> SBOMInfo:
    """
    Extract SBOM information from FastAPI request.
    
    Args:
        request: FastAPI request object
    
    Returns:
        SBOMInfo object with extracted information
    """
    headers = dict(request.headers)
    return extract_sbom_from_headers(headers)


def enhance_receipt_with_sbom(receipt: Dict[str, Any], sbom: SBOMInfo) -> Dict[str, Any]:
    """
    Add SBOM information to a receipt.
    
    Args:
        receipt: Existing receipt dictionary
        sbom: SBOM information to add
    
    Returns:
        Enhanced receipt with sbom{} field added if non-empty
    """
    if not sbom.is_empty():
        receipt = receipt.copy()
        receipt["sbom"] = sbom.to_dict()
    
    return receipt


def record_sbom_metrics(sbom: SBOMInfo) -> None:
    """
    Record SBOM metrics for observability.
    
    Args:
        sbom: SBOM information to record
    """
    try:
        from apps.gateway.metrics import sbom_headers_total
        
        # Count each type of SBOM header
        if sbom.models:
            sbom_headers_total.labels(type="model").inc(len(sbom.models))
        
        if sbom.tools:
            sbom_headers_total.labels(type="tool").inc(len(sbom.tools))
        
        if sbom.prompt_cids:
            sbom_headers_total.labels(type="prompt_cid").inc(len(sbom.prompt_cids))
    
    except ImportError:
        # Metrics not available, continue silently
        pass


def _parse_csv_header(header_value: str) -> List[str]:
    """
    Parse comma-separated header value into list of unique, non-empty strings.
    
    Args:
        header_value: Header value to parse
    
    Returns:
        List of parsed values
    """
    if not header_value:
        return []
    
    # Split on comma, strip whitespace, remove empty strings
    items = [item.strip() for item in header_value.split(",")]
    items = [item for item in items if item]
    
    # Return unique items while preserving order
    seen: Set[str] = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    
    return unique_items


# Environment configuration
def is_sbom_enabled() -> bool:
    """Check if SBOM processing is enabled."""
    return os.getenv("ODIN_SBOM_ENABLED", "1") != "0"


def get_sbom_header_names() -> Dict[str, str]:
    """Get configured SBOM header names (for customization)."""
    return {
        "model": os.getenv("ODIN_SBOM_MODEL_HEADER", "X-ODIN-Model"),
        "tool": os.getenv("ODIN_SBOM_TOOL_HEADER", "X-ODIN-Tool"),
        "prompt_cid": os.getenv("ODIN_SBOM_PROMPT_HEADER", "X-ODIN-Prompt-CID"),
    }
