"""
Enhanced OpenTelemetry tracing utilities for ODIN Protocol.

Provides custom span decorators and context managers for detailed
distributed tracing across ODIN services.
"""

import functools
import os
from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False


def get_tracer(service_name: str = "odin"):
    """Get OpenTelemetry tracer instance."""
    if not TRACING_AVAILABLE:
        return None
    return trace.get_tracer(f"{service_name}.tracer")


@contextmanager
def trace_operation(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for tracing operations with automatic error handling."""
    if not TRACING_AVAILABLE:
        yield None
        return
        
    tracer = get_tracer()
    if not tracer:
        yield None
        return
        
    with tracer.start_as_current_span(operation_name) as span:
        try:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_function(operation_name: Optional[str] = None, 
                   include_args: bool = False,
                   include_result: bool = False):
    """Decorator for automatically tracing function calls."""
    def decorator(func: Callable) -> Callable:
        if not TRACING_AVAILABLE:
            return func
            
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attributes = {
                "function.name": func.__name__,
                "function.module": func.__module__,
            }
            
            if include_args:
                # Only include simple types to avoid serialization issues
                for i, arg in enumerate(args[:3]):  # Limit to first 3 args
                    if isinstance(arg, (str, int, float, bool)):
                        attributes[f"function.arg.{i}"] = str(arg)
                        
                for key, value in list(kwargs.items())[:5]:  # Limit to first 5 kwargs
                    if isinstance(value, (str, int, float, bool)):
                        attributes[f"function.kwarg.{key}"] = str(value)
            
            with trace_operation(op_name, attributes) as span:
                result = func(*args, **kwargs)
                
                if include_result and span and isinstance(result, (str, int, float, bool)):
                    span.set_attribute("function.result", str(result))
                    
                return result
                
        return wrapper
    return decorator


def trace_bridge_execution(source_format: str, target_format: str, transformation_id: str):
    """Specialized tracing for Bridge Pro executions."""
    return trace_operation("bridge.execute", {
        "bridge.source_format": source_format,
        "bridge.target_format": target_format,
        "bridge.transformation_id": transformation_id,
        "bridge.service": "bridge_pro"
    })


def trace_sft_translation(map_id: str, source_format: str, target_format: str):
    """Specialized tracing for SFT translations."""
    return trace_operation("sft.translate", {
        "sft.map_id": map_id,
        "sft.source_format": source_format,
        "sft.target_format": target_format,
        "sft.operation": "semantic_transformation"
    })


def trace_research_operation(project_id: str, operation_type: str, tenant_id: Optional[str] = None):
    """Specialized tracing for Research Engine operations."""
    attributes = {
        "research.project_id": project_id,
        "research.operation": operation_type,
        "research.service": "research_engine"
    }
    if tenant_id:
        attributes["research.tenant_id"] = tenant_id
        
    return trace_operation(f"research.{operation_type}", attributes)


def trace_storage_operation(operation: str, collection: str, document_id: Optional[str] = None):
    """Specialized tracing for storage operations."""
    attributes = {
        "storage.operation": operation,
        "storage.collection": collection,
        "storage.backend": os.getenv("ODIN_STORAGE_TYPE", "memory")
    }
    if document_id:
        attributes["storage.document_id"] = document_id
        
    return trace_operation(f"storage.{operation}", attributes)


def trace_security_check(check_type: str, tenant_id: Optional[str] = None, 
                        policy_name: Optional[str] = None):
    """Specialized tracing for security validations."""
    attributes = {
        "security.check_type": check_type,
        "security.service": "hel_security"
    }
    if tenant_id:
        attributes["security.tenant_id"] = tenant_id
    if policy_name:
        attributes["security.policy"] = policy_name
        
    return trace_operation(f"security.{check_type}", attributes)


# Enhanced span attributes for different ODIN services
class SpanAttributes:
    """Standardized span attribute names for ODIN Protocol."""
    
    # Bridge Pro
    BRIDGE_SOURCE_FORMAT = "bridge.source_format"
    BRIDGE_TARGET_FORMAT = "bridge.target_format"
    BRIDGE_TRANSFORMATION_ID = "bridge.transformation_id"
    BRIDGE_APPROVAL_STATUS = "bridge.approval_status"
    
    # Research Engine
    RESEARCH_PROJECT_ID = "research.project_id"
    RESEARCH_EXPERIMENT_ID = "research.experiment_id"
    RESEARCH_TENANT_ID = "research.tenant_id"
    RESEARCH_OPERATION = "research.operation"
    
    # SFT Translation
    SFT_MAP_ID = "sft.map_id"
    SFT_SOURCE_FORMAT = "sft.source_format"
    SFT_TARGET_FORMAT = "sft.target_format"
    SFT_VALIDATION_RESULT = "sft.validation_result"
    
    # Security
    SECURITY_TENANT_ID = "security.tenant_id"
    SECURITY_POLICY = "security.policy"
    SECURITY_CHECK_TYPE = "security.check_type"
    SECURITY_VIOLATION = "security.violation"
    
    # Storage
    STORAGE_BACKEND = "storage.backend"
    STORAGE_COLLECTION = "storage.collection"
    STORAGE_DOCUMENT_ID = "storage.document_id"
    STORAGE_OPERATION = "storage.operation"
