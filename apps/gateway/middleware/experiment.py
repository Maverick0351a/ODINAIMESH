"""
ODIN Labs Experiment Framework

Lightweight A/B testing middleware for safe experimentation.
Tag requests with X-ODIN-Experiment header, record outcomes in receipts.
"""

import os
import zlib
import logging
from typing import Optional, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException

_log = logging.getLogger(__name__)

class ExperimentMiddleware(BaseHTTPMiddleware):
    """
    ODIN Labs experiment middleware.
    
    Usage:
    - Inbound: X-ODIN-Experiment: <id>:<variant> (e.g., sft-map-v2:A)
    - Receipt: adds "experiment": {"id": "sft-map-v2", "variant": "A"}
    - Kill-switch: ODIN_EXPERIMENT_BLOCKLIST="exp1,exp2" → 403 experiment_blocked
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.blocklist = self._load_blocklist()
    
    def _load_blocklist(self) -> set[str]:
        """Load experiment blocklist from environment."""
        blocklist_env = os.getenv("ODIN_EXPERIMENT_BLOCKLIST", "")
        if not blocklist_env.strip():
            return set()
        return {exp.strip() for exp in blocklist_env.split(",") if exp.strip()}
    
    async def dispatch(self, request: Request, call_next):
        # Parse experiment header
        exp_header = request.headers.get("x-odin-experiment", "")
        experiment = self._parse_experiment(exp_header)
        
        # Check blocklist (kill-switch)
        if experiment and experiment["id"] in self.blocklist:
            _log.warning(f"Blocked experiment: {experiment['id']}")
            raise HTTPException(
                status_code=403, 
                detail=f"experiment_blocked:{experiment['id']}"
            )
        
        # Store experiment in request state
        request.state.odin_experiment = experiment
        
        # Continue processing
        response = await call_next(request)
        return response
    
    def _parse_experiment(self, header: str) -> Optional[Dict[str, str]]:
        """
        Parse experiment header: <id>:<variant>
        
        Returns:
            {"id": "exp-id", "variant": "A"} or None if invalid
        """
        if not header or ":" not in header:
            return None
        
        try:
            exp_id, variant = header.split(":", 1)
            # Sanitize inputs (prevent injection, limit length)
            exp_id = exp_id.strip()[:64]
            variant = variant.strip()[:16]
            
            if not exp_id or not variant:
                return None
                
            return {"id": exp_id, "variant": variant}
        except Exception as e:
            _log.debug(f"Failed to parse experiment header '{header}': {e}")
            return None


def bucket_trace_id(trace_id: str, num_buckets: int = 100) -> int:
    """
    Deterministic bucketing for A/B testing.
    
    Args:
        trace_id: Request trace ID
        num_buckets: Number of buckets (default 100 for percentage)
    
    Returns:
        Bucket number (0 to num_buckets-1)
    
    Example:
        variant = "B" if bucket_trace_id(trace_id) < 10 else "A"  # 10% B, 90% A
    """
    return zlib.crc32(trace_id.encode()) % num_buckets


def get_experiment_variant(trace_id: str, experiment_id: str, rollout_pct: int = 10) -> str:
    """
    Get experiment variant based on trace ID and rollout percentage.
    
    Args:
        trace_id: Request trace ID
        experiment_id: Experiment identifier
        rollout_pct: Percentage for variant B (default 10%)
    
    Returns:
        "A" (control) or "B" (treatment)
    """
    bucket = bucket_trace_id(f"{experiment_id}:{trace_id}")
    return "B" if bucket < rollout_pct else "A"


def inject_experiment_into_receipt(receipt: Dict[str, Any], request: Request) -> None:
    """
    Inject experiment data into receipt if present.
    
    Args:
        receipt: Receipt dictionary to modify
        request: FastAPI request object
    """
    experiment = getattr(request.state, "odin_experiment", None)
    if experiment:
        receipt["experiment"] = experiment
        _log.debug(f"Added experiment to receipt: {experiment}")


# Experiment manifest validation
def validate_experiment_manifest(manifest: Dict[str, Any]) -> bool:
    """
    Validate experiment manifest structure.
    
    Expected format:
    {
        "id": "sft-map-v2",
        "variants": ["A", "B"],
        "goal": "Improve coverage and reduce time_ms",
        "metrics": [
            "translate.coverage_pct >= 95",
            "translate.time_ms_p95 <= 50"
        ],
        "rollout": {
            "start": 10,
            "kill_if": ["translate.enum_violations > 0"]
        }
    }
    """
    required_fields = ["id", "variants", "goal", "metrics", "rollout"]
    
    for field in required_fields:
        if field not in manifest:
            _log.error(f"Missing required field in experiment manifest: {field}")
            return False
    
    # Validate variants
    if not isinstance(manifest["variants"], list) or len(manifest["variants"]) < 2:
        _log.error("Experiment must have at least 2 variants")
        return False
    
    # Validate rollout
    rollout = manifest["rollout"]
    if not isinstance(rollout.get("start"), int) or not (0 <= rollout["start"] <= 100):
        _log.error("rollout.start must be integer between 0-100")
        return False
    
    return True
