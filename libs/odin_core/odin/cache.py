"""
ODIN Protocol Redis Caching Layer

Provides high-performance caching for frequently accessed data including:
- SFT maps and translations
- Agent registry lookups  
- Research project metadata
- Bridge Pro approval statuses
"""

import json
import os
import asyncio
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timedelta
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class OdinRedisCache:
    """Redis-based caching layer for ODIN Protocol."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None
        self.default_ttl = int(os.getenv("ODIN_CACHE_TTL", "3600"))  # 1 hour default
        
    async def connect(self):
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            print("Warning: Redis not available, caching disabled")
            return
            
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            print(f"✅ Connected to Redis: {self.redis_url}")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            self.client = None
            
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            
    def _make_key(self, namespace: str, key: str) -> str:
        """Generate namespaced cache key."""
        return f"odin:{namespace}:{key}"
        
    def _hash_key(self, data: Union[str, Dict[str, Any]]) -> str:
        """Generate hash for complex keys."""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:12]
        
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
            
        try:
            cache_key = self._make_key(namespace, key)
            value = await self.client.get(cache_key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"Cache get error: {e}")
        return None
        
    async def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL."""
        if not self.client:
            return False
            
        try:
            cache_key = self._make_key(namespace, key)
            serialized = json.dumps(value, default=str)
            ttl = ttl or self.default_ttl
            await self.client.setex(cache_key, ttl, serialized)
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
        return False
        
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete value from cache."""
        if not self.client:
            return False
            
        try:
            cache_key = self._make_key(namespace, key)
            deleted = await self.client.delete(cache_key)
            return deleted > 0
        except Exception as e:
            print(f"Cache delete error: {e}")
        return False
        
    async def exists(self, namespace: str, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.client:
            return False
            
        try:
            cache_key = self._make_key(namespace, key)
            return bool(await self.client.exists(cache_key))
        except Exception:
            return False
            
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        if not self.client:
            return 0
            
        try:
            keys = await self.client.keys(f"odin:{pattern}")
            if keys:
                return await self.client.delete(*keys)
        except Exception as e:
            print(f"Cache invalidate error: {e}")
        return 0


# Specialized cache managers for different ODIN services
class SFTMapCache:
    """Caching for SFT maps and translations."""
    
    def __init__(self, cache: OdinRedisCache):
        self.cache = cache
        
    async def get_map(self, map_id: str) -> Optional[Dict[str, Any]]:
        """Get SFT map from cache."""
        return await self.cache.get("sft_maps", map_id)
        
    async def set_map(self, map_id: str, map_data: Dict[str, Any], ttl: int = 7200) -> bool:
        """Cache SFT map (2 hour TTL by default)."""
        return await self.cache.set("sft_maps", map_id, map_data, ttl)
        
    async def get_translation(self, source_hash: str, map_id: str) -> Optional[Dict[str, Any]]:
        """Get cached translation result."""
        key = f"{map_id}:{source_hash}"
        return await self.cache.get("sft_translations", key)
        
    async def cache_translation(self, source_data: Dict[str, Any], map_id: str, 
                               result: Dict[str, Any], ttl: int = 1800) -> bool:
        """Cache translation result (30 min TTL)."""
        source_hash = self.cache._hash_key(source_data)
        key = f"{map_id}:{source_hash}"
        return await self.cache.set("sft_translations", key, result, ttl)
        
    async def invalidate_map(self, map_id: str) -> int:
        """Invalidate all cached data for a map."""
        await self.cache.delete("sft_maps", map_id)
        return await self.cache.invalidate_pattern(f"sft_translations:{map_id}:*")


class AgentRegistryCache:
    """Caching for agent registry lookups."""
    
    def __init__(self, cache: OdinRedisCache):
        self.cache = cache
        
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent data from cache."""
        return await self.cache.get("agents", agent_id)
        
    async def set_agent(self, agent_id: str, agent_data: Dict[str, Any], ttl: int = 1800) -> bool:
        """Cache agent data (30 min TTL)."""
        return await self.cache.set("agents", agent_id, agent_data, ttl)
        
    async def get_agent_capabilities(self, agent_id: str) -> Optional[List[str]]:
        """Get cached agent capabilities."""
        agent_data = await self.get_agent(agent_id)
        return agent_data.get("capabilities") if agent_data else None
        
    async def invalidate_agent(self, agent_id: str) -> bool:
        """Remove agent from cache."""
        return await self.cache.delete("agents", agent_id)


class ResearchEngineCache:
    """Caching for Research Engine data."""
    
    def __init__(self, cache: OdinRedisCache):
        self.cache = cache
        
    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project data from cache."""
        return await self.cache.get("projects", project_id)
        
    async def set_project(self, project_id: str, project_data: Dict[str, Any], ttl: int = 900) -> bool:
        """Cache project data (15 min TTL)."""
        return await self.cache.set("projects", project_id, project_data, ttl)
        
    async def get_byok_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get BYOK token validation data."""
        return await self.cache.get("byok_tokens", token_hash)
        
    async def cache_byok_token(self, token_hash: str, token_data: Dict[str, Any], ttl: int = 900) -> bool:
        """Cache BYOK token (15 min TTL to match token expiry)."""
        return await self.cache.set("byok_tokens", token_hash, token_data, ttl)
        
    async def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get cached experiment results."""
        return await self.cache.get("experiment_results", experiment_id)
        
    async def cache_experiment_results(self, experiment_id: str, results: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache experiment results (1 hour TTL)."""
        return await self.cache.set("experiment_results", experiment_id, results, ttl)


class BridgeProCache:
    """Caching for Bridge Pro operations."""
    
    def __init__(self, cache: OdinRedisCache):
        self.cache = cache
        
    async def get_approval_status(self, transformation_id: str) -> Optional[str]:
        """Get cached approval status."""
        data = await self.cache.get("bridge_approvals", transformation_id)
        return data.get("status") if data else None
        
    async def cache_approval_status(self, transformation_id: str, status: str, 
                                   metadata: Optional[Dict[str, Any]] = None, ttl: int = 7200) -> bool:
        """Cache approval status (2 hour TTL)."""
        data = {"status": status, "timestamp": datetime.utcnow().isoformat()}
        if metadata:
            data.update(metadata)
        return await self.cache.set("bridge_approvals", transformation_id, data, ttl)
        
    async def get_iso20022_validation(self, validation_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached ISO 20022 validation result."""
        return await self.cache.get("iso20022_validations", validation_hash)
        
    async def cache_iso20022_validation(self, validation_input: Dict[str, Any], 
                                       result: Dict[str, Any], ttl: int = 1800) -> bool:
        """Cache ISO 20022 validation (30 min TTL)."""
        validation_hash = self.cache._hash_key(validation_input)
        return await self.cache.set("iso20022_validations", validation_hash, result, ttl)


# Global cache instance
_cache_instance: Optional[OdinRedisCache] = None


async def get_cache() -> OdinRedisCache:
    """Get global cache instance."""
    global _cache_instance
    if not _cache_instance:
        _cache_instance = OdinRedisCache()
        await _cache_instance.connect()
    return _cache_instance


async def init_cache_managers() -> Dict[str, Any]:
    """Initialize all cache managers."""
    cache = await get_cache()
    
    return {
        "sft": SFTMapCache(cache),
        "agents": AgentRegistryCache(cache),
        "research": ResearchEngineCache(cache),
        "bridge": BridgeProCache(cache)
    }


# Health check for cache
async def cache_health_check() -> Dict[str, Any]:
    """Check cache health and return status."""
    cache = await get_cache()
    
    if not cache.client:
        return {"status": "unavailable", "message": "Redis not connected"}
        
    try:
        # Test basic operations
        test_key = f"health_check_{int(datetime.now().timestamp())}"
        await cache.set("health", test_key, {"test": True}, 60)
        result = await cache.get("health", test_key)
        await cache.delete("health", test_key)
        
        if result and result.get("test"):
            return {"status": "healthy", "message": "Cache operations successful"}
        else:
            return {"status": "degraded", "message": "Cache operations partially failed"}
            
    except Exception as e:
        return {"status": "error", "message": f"Cache health check failed: {e}"}
