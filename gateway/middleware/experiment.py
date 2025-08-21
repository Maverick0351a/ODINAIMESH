"""
ODIN Experiment Middleware - A/B Testing and Feature Rollouts

Provides deterministic experiment assignment and variant management for
controlled rollouts of features, models, and system changes.
"""

import hashlib
import time
from typing import Dict, Optional, Any, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def get_experiment_variant(trace_id: str, experiment_id: str, rollout_pct: int) -> str:
    """
    Get deterministic experiment variant assignment.
    
    Args:
        trace_id: Unique identifier for request/user
        experiment_id: Experiment identifier
        rollout_pct: Percentage for variant B (0-100)
    
    Returns:
        "A" or "B" variant assignment
    """
    # Create deterministic hash
    hash_input = f"{trace_id}:{experiment_id}"
    hash_digest = hashlib.md5(hash_input.encode()).hexdigest()
    
    # Convert first 8 chars to int and get percentage
    hash_int = int(hash_digest[:8], 16)
    percentage = hash_int % 100
    
    return "B" if percentage < rollout_pct else "A"


class ExperimentMiddleware(BaseHTTPMiddleware):
    """
    Middleware for A/B testing and feature rollouts.
    
    Automatically assigns experiment variants based on trace IDs
    and adds variant information to request context.
    """
    
    def __init__(self, app, experiments: Optional[Dict[str, int]] = None):
        super().__init__(app)
        # Default experiments with rollout percentages
        self.experiments = experiments or {
            "model-comparison": 10,      # 10% get variant B
            "ui-redesign": 25,          # 25% get variant B
            "cache-strategy": 50,       # 50% get variant B
        }
        self.active_experiments: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Process request and add experiment context."""
        start_time = time.time()
        
        # Extract trace ID from headers
        trace_id = (
            request.headers.get("x-trace-id") or
            request.headers.get("x-request-id") or
            request.headers.get("x-correlation-id") or
            f"auto-{int(time.time() * 1000)}"
        )
        
        # Assign experiment variants
        variants = {}
        for experiment_id, rollout_pct in self.experiments.items():
            variant = get_experiment_variant(trace_id, experiment_id, rollout_pct)
            variants[experiment_id] = variant
        
        # Add to request state
        request.state.trace_id = trace_id
        request.state.experiment_variants = variants
        
        # Process request
        response = await call_next(request)
        
        # Add experiment headers to response
        response.headers["X-Trace-ID"] = trace_id
        for exp_id, variant in variants.items():
            response.headers[f"X-Experiment-{exp_id}"] = variant
        
        # Track experiment metrics
        execution_time = time.time() - start_time
        self._track_experiment_metrics(trace_id, variants, execution_time, response.status_code)
        
        return response
    
    def _track_experiment_metrics(self, trace_id: str, variants: Dict[str, str], 
                                execution_time: float, status_code: int):
        """Track experiment assignment and performance metrics."""
        for experiment_id, variant in variants.items():
            key = f"{experiment_id}:{variant}"
            
            if key not in self.active_experiments:
                self.active_experiments[key] = {
                    "experiment_id": experiment_id,
                    "variant": variant,
                    "requests": 0,
                    "total_time": 0.0,
                    "errors": 0,
                    "success_count": 0
                }
            
            exp_data = self.active_experiments[key]
            exp_data["requests"] += 1
            exp_data["total_time"] += execution_time
            
            if status_code >= 400:
                exp_data["errors"] += 1
            else:
                exp_data["success_count"] += 1
    
    def get_experiment_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get current experiment statistics."""
        stats = {}
        
        for key, data in self.active_experiments.items():
            experiment_id = data["experiment_id"]
            variant = data["variant"]
            
            if experiment_id not in stats:
                stats[experiment_id] = {"variants": {}}
            
            avg_time = data["total_time"] / max(data["requests"], 1)
            error_rate = data["errors"] / max(data["requests"], 1)
            
            stats[experiment_id]["variants"][variant] = {
                "requests": data["requests"],
                "avg_response_time": avg_time,
                "error_rate": error_rate,
                "success_rate": 1.0 - error_rate
            }
        
        return stats
    
    def add_experiment(self, experiment_id: str, rollout_pct: int):
        """Add a new experiment."""
        self.experiments[experiment_id] = rollout_pct
    
    def remove_experiment(self, experiment_id: str):
        """Remove an experiment."""
        if experiment_id in self.experiments:
            del self.experiments[experiment_id]
    
    def update_rollout(self, experiment_id: str, rollout_pct: int):
        """Update rollout percentage for an experiment."""
        if experiment_id in self.experiments:
            self.experiments[experiment_id] = rollout_pct


# Utility functions for use in request handlers
def get_experiment_variant_from_request(request: Request, experiment_id: str) -> Optional[str]:
    """Get experiment variant from request state."""
    if hasattr(request.state, "experiment_variants"):
        return request.state.experiment_variants.get(experiment_id)
    return None


def is_variant_b(request: Request, experiment_id: str) -> bool:
    """Check if request is assigned to variant B."""
    variant = get_experiment_variant_from_request(request, experiment_id)
    return variant == "B"


def get_trace_id(request: Request) -> Optional[str]:
    """Get trace ID from request state."""
    if hasattr(request.state, "trace_id"):
        return request.state.trace_id
    return None
