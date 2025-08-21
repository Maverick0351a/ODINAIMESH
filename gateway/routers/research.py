"""
ODIN Research Engine - Multi-tenant research API with BYOM support.

Provides project-scoped experimentation with built-in benchmarks,
cryptographic receipts, and safety guardrails.
"""

import asyncio
import hashlib
import io
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

from libs.odin_core.odin.bridge_engine import BridgeEngine
from gateway.middleware.experiment import ExperimentMiddleware, get_experiment_variant
from bench.runner.run_bench import BenchRunner

try:
    from libs.odin_core.odin.storage.firestore import create_storage_backend
    # Use Firestore in production, in-memory for development
    storage_backend = create_storage_backend()
except ImportError:
    # Fallback to in-memory storage
    storage_backend = None


# ==================== Models ====================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=200)

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    quota_requests_used: int = 0
    quota_requests_limit: int = 1000
    tier: str = "free"  # free, pro, enterprise

class BYOKTokenRequest(BaseModel):
    provider: str = Field(..., description="API provider")
    api_key: str = Field(..., min_length=10)
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        allowed = ["openai", "anthropic", "gemini", "vertex"]
        if v not in allowed:
            raise ValueError(f"Provider must be one of: {allowed}")
        return v

class BYOKToken(BaseModel):
    token: str
    expires_at: datetime
    provider: str

class ExperimentCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=50)
    variant: str = Field(..., description="Experiment variant")
    goal: str = Field(..., max_length=200)
    rollout_pct: int = Field(default=10, ge=1, le=25)
    
    @field_validator('variant')
    @classmethod
    def validate_variant(cls, v):
        if v not in ["A", "B"]:
            raise ValueError("Variant must be 'A' or 'B'")
        return v

class RunCreate(BaseModel):
    experiment_id: Optional[str] = None
    dataset_id: str
    realm: str = Field(default="business")
    map_id: str = Field(default="iso20022_pain001_v1")
    router_policy: str = Field(default="cost_optimized")
    byok_token: Optional[str] = None

class RunReport(BaseModel):
    run_id: str
    project_id: str
    experiment_id: Optional[str]
    dataset_id: str
    status: str
    metrics: Dict[str, Any]
    receipt_chain: List[str]
    created_at: datetime
    completed_at: Optional[datetime]

class Dataset(BaseModel):
    id: str
    project_id: str
    name: str
    format: str  # json, csv
    size_bytes: int
    record_count: int
    created_at: datetime


# ==================== Storage (In-Memory for MVP) ====================

class ResearchStorage:
    """In-memory storage for Research Engine. Use Redis/DB for production."""
    
    def __init__(self):
        self.projects: Dict[str, Project] = {}
        self.byok_tokens: Dict[str, Dict[str, Any]] = {}
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.datasets: Dict[str, Dataset] = {}
        self.rate_limits: Dict[str, List[float]] = {}  # IP -> timestamps
    
    def create_project(self, name: str, description: Optional[str] = None) -> Project:
        project_id = f"proj_{secrets.token_urlsafe(12)}"
        project = Project(
            id=project_id,
            name=name,
            description=description,
            created_at=datetime.utcnow()
        )
        self.projects[project_id] = project
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        return self.projects.get(project_id)
    
    def store_byok_token(self, provider: str, api_key: str, ttl_minutes: int = 15) -> BYOKToken:
        token = f"byok_{secrets.token_urlsafe(32)}"
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        
        # Encrypt API key (simplified - use proper encryption in production)
        encrypted_key = hashlib.sha256(f"{api_key}:{token}".encode()).hexdigest()
        
        self.byok_tokens[token] = {
            "provider": provider,
            "encrypted_key": encrypted_key,
            "original_key": api_key,  # Store temporarily for demo
            "expires_at": expires_at
        }
        
        return BYOKToken(token=token, expires_at=expires_at, provider=provider)
    
    def get_byok_token(self, token: str) -> Optional[Dict[str, Any]]:
        if token not in self.byok_tokens:
            return None
        
        token_data = self.byok_tokens[token]
        if datetime.utcnow() > token_data["expires_at"]:
            del self.byok_tokens[token]
            return None
        
        return token_data
    
    def store_dataset(self, project_id: str, name: str, format: str, 
                     size_bytes: int, record_count: int) -> Dataset:
        dataset_id = f"ds_{secrets.token_urlsafe(12)}"
        dataset = Dataset(
            id=dataset_id,
            project_id=project_id,
            name=name,
            format=format,
            size_bytes=size_bytes,
            record_count=record_count,
            created_at=datetime.utcnow()
        )
        self.datasets[dataset_id] = dataset
        return dataset
    
    def store_run(self, project_id: str, experiment_id: Optional[str], 
                  dataset_id: str, **kwargs) -> str:
        run_id = f"run_{secrets.token_urlsafe(12)}"
        self.runs[run_id] = {
            "id": run_id,
            "project_id": project_id,
            "experiment_id": experiment_id,
            "dataset_id": dataset_id,
            "status": "running",
            "created_at": datetime.utcnow(),
            **kwargs
        }
        return run_id
    
    def update_run(self, run_id: str, **updates):
        if run_id in self.runs:
            self.runs[run_id].update(updates)
    
    def complete_run(self, run_id: str, metrics: Dict[str, Any], receipt_chain: List[str]):
        """Complete an experiment run with metrics and receipts."""
        if run_id in self.runs:
            self.runs[run_id].update({
                "status": "completed",
                "metrics": metrics,
                "receipt_chain": receipt_chain,
                "completed_at": datetime.utcnow()
            })
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.runs.get(run_id)
    
    def check_rate_limit(self, ip: str, endpoint: str, limit_per_minute: int = 30) -> bool:
        """Check if IP is within rate limit for endpoint."""
        now = time.time()
        key = f"{ip}:{endpoint}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # Clean old timestamps
        self.rate_limits[key] = [ts for ts in self.rate_limits[key] if now - ts < 60]
        
        if len(self.rate_limits[key]) >= limit_per_minute:
            return False
        
        self.rate_limits[key].append(now)
        return True


# ==================== Dependencies ====================

# Global storage instance
_storage = None

def get_storage():
    """Get storage backend instance."""
    global _storage
    if _storage is None:
        if storage_backend:
            _storage = storage_backend
        else:
            _storage = ResearchStorage()
    return _storage

storage = get_storage()
security = HTTPBearer()

def get_client_ip(x_forwarded_for: Optional[str] = Header(None)) -> str:
    """Extract client IP for rate limiting."""
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return "127.0.0.1"

def rate_limit(endpoint: str, limit: int = 30):
    """Rate limiting decorator."""
    def decorator(ip: str = Depends(get_client_ip)):
        if not storage.check_rate_limit(ip, endpoint, limit):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return ip
    return decorator

def get_project(project_id: str) -> Project:
    """Get project or raise 404."""
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

def check_quota(project: Project, requests_needed: int = 1):
    """Check project quota."""
    if project.quota_requests_used + requests_needed > project.quota_requests_limit:
        raise HTTPException(status_code=429, detail="Project quota exceeded")


# ==================== Router ====================

router = APIRouter(prefix="/v1", tags=["research"])


@router.post("/projects", response_model=Project)
async def create_project(
    project_data: ProjectCreate,
    _: str = Depends(rate_limit("create_project", 5))  # 5 per minute
):
    """Create a new research project with quotas."""
    
    # Validate realm allowlist (business only for free tier)
    if len(storage.projects) >= 10:  # Limit total projects for demo
        raise HTTPException(status_code=429, detail="Project creation limit reached")
    
    project = storage.create_project(project_data.name, project_data.description)
    return project


@router.post("/byok/token", response_model=BYOKToken)
async def create_byok_token(
    token_request: BYOKTokenRequest,
    _: str = Depends(rate_limit("byok_token", 30))  # 30 per minute
):
    """Mint short-lived BYOK token (server-side encryption)."""
    
    # Validate API key format (basic checks)
    if token_request.provider == "openai" and not token_request.api_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="Invalid OpenAI API key format")
    
    token = storage.store_byok_token(token_request.provider, token_request.api_key)
    return token


@router.post("/experiments")
async def create_experiment(
    experiment: ExperimentCreate,
    project_id: str = Header(..., alias="x-odin-project-id")
):
    """Create experiment configuration."""
    
    project = get_project(project_id)
    
    storage.experiments[f"{project_id}:{experiment.id}"] = {
        "id": experiment.id,
        "project_id": project_id,
        "variant": experiment.variant,
        "goal": experiment.goal,
        "rollout_pct": experiment.rollout_pct,
        "created_at": datetime.utcnow()
    }
    
    return {"status": "created", "experiment_id": experiment.id}


@router.post("/runs")
async def create_run(
    run_data: RunCreate,
    project_id: str = Header(..., alias="x-odin-project-id"),
    _: str = Depends(rate_limit("runs", 10))  # 10 per minute
):
    """Execute research run with experiment tracking."""
    
    project = get_project(project_id)
    check_quota(project, 1)
    
    # Validate realm allowlist (business only for free tier)
    if project.tier == "free" and run_data.realm != "business":
        raise HTTPException(status_code=403, detail="Free tier limited to business realm")
    
    # Validate dataset exists
    dataset = storage.datasets.get(run_data.dataset_id)
    if not dataset or dataset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Create run
    run_id = storage.store_run(
        project_id=project_id,
        experiment_id=run_data.experiment_id,
        dataset_id=run_data.dataset_id,
        realm=run_data.realm,
        map_id=run_data.map_id,
        router_policy=run_data.router_policy
    )
    
    # Execute async (simplified for demo)
    asyncio.create_task(execute_run(run_id, run_data))
    
    # Update quota
    project.quota_requests_used += 1
    
    return {"run_id": run_id, "status": "queued"}


async def execute_run(run_id: str, run_data: RunCreate):
    """Execute research run (background task)."""
    
    try:
        # Simulate execution
        await asyncio.sleep(2)  # Simulate processing time
        
        # Generate mock results
        metrics = {
            "coverage_pct": 95.2,
            "p95_latency_ms": 47.3,
            "cost_per_request": 0.0023,
            "success_rate": 0.998,
            "mediator_score": 0.87,
            "enum_violations": 0
        }
        
        receipt_chain = [
            f"bafybei{secrets.token_urlsafe(32)[:40]}",  # Mock IPFS CID
            f"bafybei{secrets.token_urlsafe(32)[:40]}",
            f"bafybei{secrets.token_urlsafe(32)[:40]}"
        ]
        
        storage.update_run(run_id, 
            status="completed",
            metrics=metrics,
            receipt_chain=receipt_chain,
            completed_at=datetime.utcnow()
        )
        
    except Exception as e:
        storage.update_run(run_id, 
            status="failed", 
            error=str(e),
            completed_at=datetime.utcnow()
        )


@router.get("/runs/{run_id}/report", response_model=RunReport)
async def get_run_report(
    run_id: str,
    project_id: str = Header(..., alias="x-odin-project-id")
):
    """Get run results with receipt chain."""
    
    run = storage.get_run(run_id)
    if not run or run["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunReport(
        run_id=run["id"],
        project_id=run["project_id"],
        experiment_id=run.get("experiment_id"),
        dataset_id=run["dataset_id"],
        status=run["status"],
        metrics=run.get("metrics", {}),
        receipt_chain=run.get("receipt_chain", []),
        created_at=run["created_at"],
        completed_at=run.get("completed_at")
    )


@router.post("/datasets", response_model=Dataset)
async def upload_dataset(
    file: UploadFile = File(...),
    project_id: str = Header(..., alias="x-odin-project-id"),
    _: str = Depends(rate_limit("datasets", 10))  # 10 per minute
):
    """Upload dataset for benchmarking."""
    
    project = get_project(project_id)
    
    # Validate file
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large")
    
    if not file.filename.endswith(('.json', '.csv')):
        raise HTTPException(status_code=400, detail="Only JSON/CSV files supported")
    
    # Read and validate content
    content = await file.read()
    
    try:
        if file.filename.endswith('.json'):
            data = json.loads(content)
            record_count = len(data) if isinstance(data, list) else 1
        else:
            df = pd.read_csv(io.StringIO(content.decode()))
            record_count = len(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file format: {str(e)}")
    
    # Store dataset metadata
    dataset = storage.store_dataset(
        project_id=project_id,
        name=file.filename,
        format=file.filename.split('.')[-1],
        size_bytes=file.size,
        record_count=record_count
    )
    
    return dataset


@router.get("/receipts/export")
async def export_receipts(
    project_id: str,
    format: str = "ndjson",
    _: str = Depends(rate_limit("export", 5))  # 5 per minute
):
    """Export project receipts (redacted headers)."""
    
    project = get_project(project_id)
    
    if format not in ["ndjson", "parquet"]:
        raise HTTPException(status_code=400, detail="Supported formats: ndjson, parquet")
    
    # Get all runs for project
    project_runs = [run for run in storage.runs.values() 
                   if run["project_id"] == project_id]
    
    # Mock export data (redacted)
    export_data = []
    for run in project_runs:
        export_data.append({
            "run_id": run["id"],
            "experiment_id": run.get("experiment_id"),
            "dataset_id": run["dataset_id"],
            "metrics": run.get("metrics", {}),
            "receipt_chain": run.get("receipt_chain", []),
            "created_at": run["created_at"].isoformat(),
            # Headers redacted for security
            "redacted_fields": ["authorization", "x-api-key", "x-odin-byok-token"]
        })
    
    if format == "ndjson":
        content = "\n".join(json.dumps(item) for item in export_data)
        media_type = "application/x-ndjson"
    else:
        # For parquet, would use pandas/pyarrow
        content = json.dumps(export_data, indent=2)
        media_type = "application/json"
    
    return {
        "content": content,
        "media_type": media_type,
        "filename": f"receipts_{project_id}_{datetime.utcnow().strftime('%Y%m%d')}.{format}"
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "projects": len(storage.projects),
        "active_tokens": len(storage.byok_tokens),
        "total_runs": len(storage.runs)
    }
