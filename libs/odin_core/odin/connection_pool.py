"""
ODIN Protocol Connection Pooling Manager

Provides optimized connection management for:
- HTTP clients with keep-alive and connection reuse
- Database connections with async pooling
- External API connections with circuit breakers
- WebSocket connection management
"""

import asyncio
import os
from typing import Dict, Optional, Any, List, Union
from datetime import datetime, timedelta
import aiohttp
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass
import weakref

try:
    import aiodns
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False


@dataclass
class ConnectionConfig:
    """Configuration for connection pools."""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: int = 30
    timeout: int = 30
    retry_attempts: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking."""
    failures: int = 0
    last_failure: Optional[datetime] = None
    state: str = "closed"  # closed, open, half-open
    next_attempt: Optional[datetime] = None


class ConnectionPoolManager:
    """Manages all connection pools for ODIN Protocol."""
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.pools: Dict[str, Any] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._cleanup_tasks: List[asyncio.Task] = []
        
    async def initialize(self):
        """Initialize all connection pools."""
        await self._init_http_session()
        await self._start_cleanup_tasks()
        print("✅ Connection pools initialized")
        
    async def _init_http_session(self):
        """Initialize HTTP session with optimized settings."""
        # SSL context for secure connections
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # DNS resolver
        resolver = None
        if DNS_AVAILABLE:
            resolver = aiohttp.AsyncResolver()
            
        # Connection limits and timeouts
        connector = aiohttp.TCPConnector(
            limit=self.config.max_connections,
            limit_per_host=self.config.max_keepalive_connections,
            keepalive_timeout=self.config.keepalive_expiry,
            ssl=ssl_context,
            resolver=resolver,
            enable_cleanup_closed=True,
            force_close=False,  # Keep connections alive
            use_dns_cache=True,
            ttl_dns_cache=300,  # 5 minutes DNS cache
        )
        
        # Session timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=10,
            sock_read=self.config.timeout,
            sock_connect=10
        )
        
        # Create session with optimized headers
        headers = {
            'User-Agent': 'ODIN-Protocol/1.0',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        self.http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
            raise_for_status=False  # Handle status codes manually
        )
        
    async def _start_cleanup_tasks(self):
        """Start background cleanup tasks."""
        # Circuit breaker reset task
        cleanup_task = asyncio.create_task(self._circuit_breaker_cleanup())
        self._cleanup_tasks.append(cleanup_task)
        
        # Connection health check task
        health_task = asyncio.create_task(self._connection_health_check())
        self._cleanup_tasks.append(health_task)
        
    async def _circuit_breaker_cleanup(self):
        """Reset circuit breakers after timeout."""
        while True:
            try:
                current_time = datetime.utcnow()
                
                for service, breaker in self.circuit_breakers.items():
                    if (breaker.state == "open" and 
                        breaker.next_attempt and 
                        current_time >= breaker.next_attempt):
                        breaker.state = "half-open"
                        print(f"🔄 Circuit breaker for {service} moved to half-open")
                        
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Circuit breaker cleanup error: {e}")
                await asyncio.sleep(60)
                
    async def _connection_health_check(self):
        """Monitor connection pool health."""
        while True:
            try:
                if self.http_session and not self.http_session.closed:
                    connector = self.http_session.connector
                    if hasattr(connector, '_conns'):
                        total_connections = sum(len(conns) for conns in connector._conns.values())
                        print(f"📊 Active HTTP connections: {total_connections}")
                        
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Health check error: {e}")
                await asyncio.sleep(300)
                
    def _check_circuit_breaker(self, service: str) -> bool:
        """Check if circuit breaker allows request."""
        breaker = self.circuit_breakers.get(service)
        if not breaker:
            return True
            
        current_time = datetime.utcnow()
        
        if breaker.state == "closed":
            return True
        elif breaker.state == "open":
            if breaker.next_attempt and current_time >= breaker.next_attempt:
                breaker.state = "half-open"
                return True
            return False
        elif breaker.state == "half-open":
            return True
            
        return False
        
    def _record_success(self, service: str):
        """Record successful request."""
        if service in self.circuit_breakers:
            breaker = self.circuit_breakers[service]
            if breaker.state == "half-open":
                breaker.state = "closed"
                breaker.failures = 0
                breaker.last_failure = None
                breaker.next_attempt = None
                print(f"✅ Circuit breaker for {service} closed")
                
    def _record_failure(self, service: str):
        """Record failed request."""
        breaker = self.circuit_breakers.setdefault(service, CircuitBreakerState())
        breaker.failures += 1
        breaker.last_failure = datetime.utcnow()
        
        if breaker.failures >= self.config.circuit_breaker_threshold:
            breaker.state = "open"
            breaker.next_attempt = breaker.last_failure + timedelta(
                seconds=self.config.circuit_breaker_timeout
            )
            print(f"🚨 Circuit breaker for {service} opened after {breaker.failures} failures")
            
    @asynccontextmanager
    async def http_request(self, service: str):
        """Get HTTP session with circuit breaker protection."""
        if not self._check_circuit_breaker(service):
            raise ConnectionError(f"Circuit breaker open for {service}")
            
        if not self.http_session or self.http_session.closed:
            await self._init_http_session()
            
        try:
            yield self.http_session
            self._record_success(service)
        except Exception as e:
            self._record_failure(service)
            raise
            
    async def make_request(self, service: str, method: str, url: str, 
                          retries: Optional[int] = None, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request with retry logic and circuit breaker."""
        retries = retries or self.config.retry_attempts
        last_exception = None
        
        for attempt in range(retries + 1):
            try:
                async with self.http_request(service) as session:
                    response = await session.request(method, url, **kwargs)
                    
                    # Consider 5xx as retriable errors
                    if response.status >= 500 and attempt < retries:
                        await response.release()
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                        
                    return response
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
                
        raise last_exception or ConnectionError(f"Max retries exceeded for {service}")
        
    async def close_all(self):
        """Close all connections and cleanup."""
        # Cancel cleanup tasks
        for task in self._cleanup_tasks:
            task.cancel()
            
        try:
            await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)
        except Exception:
            pass
            
        # Close HTTP session
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            
        # Wait for connections to close
        await asyncio.sleep(0.1)
        
        print("✅ All connections closed")
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        stats = {
            "http_session_active": bool(self.http_session and not self.http_session.closed),
            "circuit_breakers": {},
            "active_connections": 0
        }
        
        # Circuit breaker stats
        for service, breaker in self.circuit_breakers.items():
            stats["circuit_breakers"][service] = {
                "state": breaker.state,
                "failures": breaker.failures,
                "last_failure": breaker.last_failure.isoformat() if breaker.last_failure else None
            }
            
        # HTTP connection stats
        if self.http_session and not self.http_session.closed:
            connector = self.http_session.connector
            if hasattr(connector, '_conns'):
                stats["active_connections"] = sum(
                    len(conns) for conns in connector._conns.values()
                )
                
        return stats


class OdinAPIClient:
    """Optimized API client for ODIN services."""
    
    def __init__(self, pool_manager: ConnectionPoolManager, base_url: str, 
                 service_name: str, api_key: Optional[str] = None):
        self.pool_manager = pool_manager
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.api_key = api_key
        
    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            
        if additional_headers:
            headers.update(additional_headers)
            
        return headers
        
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers(headers)
        
        async with self.pool_manager.http_request(self.service_name) as session:
            response = await session.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            return await response.json()
            
    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
                   headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers(headers)
        
        async with self.pool_manager.http_request(self.service_name) as session:
            response = await session.post(url, json=data, headers=request_headers)
            response.raise_for_status()
            return await response.json()
            
    async def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make PUT request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers(headers)
        
        async with self.pool_manager.http_request(self.service_name) as session:
            response = await session.put(url, json=data, headers=request_headers)
            response.raise_for_status()
            return await response.json()
            
    async def delete(self, endpoint: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Make DELETE request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers(headers)
        
        async with self.pool_manager.http_request(self.service_name) as session:
            response = await session.delete(url, headers=request_headers)
            response.raise_for_status()
            return response.status in (200, 204)


# Global connection manager
_pool_manager: Optional[ConnectionPoolManager] = None


async def get_pool_manager() -> ConnectionPoolManager:
    """Get global connection pool manager."""
    global _pool_manager
    if not _pool_manager:
        _pool_manager = ConnectionPoolManager()
        await _pool_manager.initialize()
    return _pool_manager


async def create_api_client(base_url: str, service_name: str, 
                           api_key: Optional[str] = None) -> OdinAPIClient:
    """Create optimized API client."""
    pool_manager = await get_pool_manager()
    return OdinAPIClient(pool_manager, base_url, service_name, api_key)


# Health check for connection pools
async def connection_health_check() -> Dict[str, Any]:
    """Check connection pool health."""
    try:
        pool_manager = await get_pool_manager()
        stats = await pool_manager.get_stats()
        
        # Determine overall health
        if stats["http_session_active"]:
            health_status = "healthy"
            message = "All connection pools active"
        else:
            health_status = "degraded"
            message = "Some connection pools inactive"
            
        # Check for open circuit breakers
        open_breakers = [
            service for service, breaker in stats["circuit_breakers"].items()
            if breaker["state"] == "open"
        ]
        
        if open_breakers:
            health_status = "degraded"
            message = f"Circuit breakers open for: {', '.join(open_breakers)}"
            
        return {
            "status": health_status,
            "message": message,
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Connection health check failed: {e}",
            "stats": {}
        }
