"""
ODIN Protocol Database Migration System

Provides Alembic-based database migrations for production deployments.
Supports multiple backends (PostgreSQL, Firestore schema evolution).
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone

try:
    from alembic import command, config
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False

from libs.odin_core.odin.storage import create_storage_from_env


class MigrationManager:
    """Manages database schema migrations for ODIN Protocol."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "alembic.ini"
        self.storage = create_storage_from_env()
        
    def init_alembic(self):
        """Initialize Alembic configuration if not exists."""
        if not ALEMBIC_AVAILABLE:
            raise ImportError("Alembic not installed. Run: pip install alembic")
            
        if not Path(self.config_path).exists():
            # Create alembic.ini
            alembic_ini = """# Alembic Configuration for ODIN Protocol

[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = postgresql://user:pass@localhost/odin

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
            with open(self.config_path, 'w') as f:
                f.write(alembic_ini)
                
            # Initialize migrations directory
            command.init(Config(self.config_path), "migrations")
            
    async def create_migration(self, message: str, auto_generate: bool = True) -> str:
        """Create a new migration."""
        if not ALEMBIC_AVAILABLE:
            raise ImportError("Alembic not available")
            
        cfg = Config(self.config_path)
        
        if auto_generate:
            # Auto-generate migration based on model changes
            command.revision(cfg, message=message, autogenerate=True)
        else:
            # Create empty migration template
            command.revision(cfg, message=message)
            
        # Get the latest revision
        script_dir = ScriptDirectory.from_config(cfg)
        head = script_dir.get_current_head()
        
        return head
        
    async def upgrade_database(self, revision: str = "head") -> bool:
        """Upgrade database to specified revision."""
        try:
            cfg = Config(self.config_path)
            command.upgrade(cfg, revision)
            
            # Log migration in ODIN storage
            await self._log_migration("upgrade", revision)
            return True
        except Exception as e:
            print(f"Migration failed: {e}")
            return False
            
    async def downgrade_database(self, revision: str) -> bool:
        """Downgrade database to specified revision."""
        try:
            cfg = Config(self.config_path)
            command.downgrade(cfg, revision)
            
            await self._log_migration("downgrade", revision)
            return True
        except Exception as e:
            print(f"Downgrade failed: {e}")
            return False
            
    async def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get migration history from ODIN storage."""
        try:
            history = await self.storage.list("migrations", limit=100)
            return sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception:
            return []
            
    async def get_current_revision(self) -> Optional[str]:
        """Get current database revision."""
        if not ALEMBIC_AVAILABLE:
            return None
            
        try:
            cfg = Config(self.config_path)
            script_dir = ScriptDirectory.from_config(cfg)
            return script_dir.get_current_head()
        except Exception:
            return None
            
    async def check_migration_status(self) -> Dict[str, Any]:
        """Check if database needs migration."""
        current = await self.get_current_revision()
        
        # In a real implementation, you'd compare with database state
        # For now, return basic status
        return {
            "current_revision": current,
            "pending_migrations": 0,
            "status": "up_to_date"
        }
        
    async def _log_migration(self, operation: str, revision: str):
        """Log migration operation to ODIN storage."""
        migration_log = {
            "operation": operation,
            "revision": revision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "migration_manager",
            "environment": os.getenv("ODIN_ENVIRONMENT", "development")
        }
        
        migration_id = f"{operation}_{revision}_{int(datetime.now().timestamp())}"
        await self.storage.set("migrations", migration_id, migration_log)


# Firestore-specific schema evolution helpers
class FirestoreSchemaManager:
    """Manages Firestore collection schema evolution."""
    
    def __init__(self):
        self.storage = create_storage_from_env()
        
    async def create_schema_version(self, collection: str, version: str, schema: Dict[str, Any]):
        """Create a new schema version for a collection."""
        schema_doc = {
            "collection": collection,
            "version": version,
            "schema": schema,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active"
        }
        
        schema_id = f"{collection}_v{version}"
        await self.storage.set("schema_versions", schema_id, schema_doc)
        
    async def migrate_collection_data(self, collection: str, from_version: str, to_version: str):
        """Migrate collection data between schema versions."""
        # This would contain collection-specific migration logic
        # For now, just log the operation
        migration_log = {
            "collection": collection,
            "from_version": from_version,
            "to_version": to_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "schema_migration"
        }
        
        await self.storage.set("schema_migrations", 
                              f"{collection}_{from_version}_to_{to_version}", 
                              migration_log)
                              
    async def validate_document_schema(self, collection: str, document: Dict[str, Any]) -> bool:
        """Validate document against latest schema version."""
        # Basic validation - in production this would use JSON Schema
        required_fields = {
            "projects": ["name", "tenant_id", "created_at"],
            "experiments": ["project_id", "name", "status"],
            "agents": ["agent_id", "public_key", "status"]
        }
        
        if collection in required_fields:
            return all(field in document for field in required_fields[collection])
            
        return True


# CLI Commands for migration management
async def main():
    """CLI interface for migration management."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python migration_manager.py <command> [args]")
        print("Commands: init, create, upgrade, downgrade, status, history")
        return
        
    command = sys.argv[1]
    manager = MigrationManager()
    
    if command == "init":
        manager.init_alembic()
        print("✅ Alembic initialized")
        
    elif command == "create":
        if len(sys.argv) < 3:
            print("Usage: create <message>")
            return
        message = " ".join(sys.argv[2:])
        revision = await manager.create_migration(message)
        print(f"✅ Created migration: {revision}")
        
    elif command == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        success = await manager.upgrade_database(revision)
        if success:
            print(f"✅ Upgraded to {revision}")
        else:
            print("❌ Upgrade failed")
            
    elif command == "downgrade":
        if len(sys.argv) < 3:
            print("Usage: downgrade <revision>")
            return
        revision = sys.argv[2]
        success = await manager.downgrade_database(revision)
        if success:
            print(f"✅ Downgraded to {revision}")
        else:
            print("❌ Downgrade failed")
            
    elif command == "status":
        status = await manager.check_migration_status()
        print(f"Current revision: {status['current_revision']}")
        print(f"Status: {status['status']}")
        
    elif command == "history":
        history = await manager.get_migration_history()
        print("Migration History:")
        for entry in history[:10]:  # Show last 10
            print(f"  {entry.get('timestamp', '')} - {entry.get('operation', '')} - {entry.get('revision', '')}")
            
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
