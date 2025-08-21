#!/usr/bin/env python3
"""
ODIN Research Engine deployment script.
Orchestrates full system deployment with health checks.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx


class OdinDeployer:
    """ODIN Research Engine deployment orchestrator."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.compose_file = self.project_root / "docker-compose.research.yml"
        self.gateway_url = "http://localhost:8000"
        self.health_timeout = 120  # 2 minutes
        
    async def deploy(self):
        """Deploy complete ODIN Research Engine stack."""
        print("🚀 Starting ODIN Research Engine deployment...\n")
        
        try:
            # Step 1: Validate deployment files
            await self.validate_deployment_files()
            
            # Step 2: Start services with docker-compose
            await self.start_services()
            
            # Step 3: Wait for services to be healthy
            await self.wait_for_health()
            
            # Step 4: Run smoke tests
            await self.run_smoke_tests()
            
            # Step 5: Display success message
            self.display_success()
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            await self.cleanup()
            return 1
        
        return 0
    
    async def validate_deployment_files(self):
        """Validate that all required deployment files exist."""
        print("📋 Validating deployment files...")
        
        required_files = [
            "docker-compose.research.yml",
            "Dockerfile.research",
            "scripts/init_db.sql",
            "config/production.env",
            "config/prometheus.yml"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            raise Exception(f"Missing deployment files: {missing_files}")
        
        print("✅ All deployment files present")
    
    async def start_services(self):
        """Start services using docker-compose."""
        print("🐳 Starting services with docker-compose...")
        
        # Check if Docker is running
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise Exception("Docker is not running or not installed")
        
        # Start services
        cmd = [
            "docker-compose",
            "-f", str(self.compose_file),
            "up", "-d", "--build"
        ]
        
        print(f"Running: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            raise Exception(f"Docker compose failed: {process.stderr}")
        
        print("✅ Services started successfully")
        print(f"📝 Logs: {process.stdout}")
    
    async def wait_for_health(self):
        """Wait for all services to become healthy."""
        print("⏳ Waiting for services to become healthy...")
        
        services = [
            ("Gateway", f"{self.gateway_url}/v1/health"),
            ("Research API", f"{self.gateway_url}/v1/research/health"),
        ]
        
        start_time = time.time()
        
        while time.time() - start_time < self.health_timeout:
            all_healthy = True
            
            for service_name, health_url in services:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(health_url)
                        if response.status_code == 200:
                            print(f"✅ {service_name} is healthy")
                        else:
                            print(f"⏳ {service_name} not ready (status: {response.status_code})")
                            all_healthy = False
                except Exception as e:
                    print(f"⏳ {service_name} not ready ({e})")
                    all_healthy = False
            
            if all_healthy:
                print("🎉 All services are healthy!")
                return
            
            print("Waiting 10 seconds before next health check...")
            await asyncio.sleep(10)
        
        raise Exception(f"Services did not become healthy within {self.health_timeout} seconds")
    
    async def run_smoke_tests(self):
        """Run basic smoke tests to validate deployment."""
        print("🧪 Running smoke tests...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            
            # Test 1: Health endpoints
            health_response = await client.get(f"{self.gateway_url}/v1/health")
            assert health_response.status_code == 200
            print("✅ Gateway health check passed")
            
            research_health = await client.get(f"{self.gateway_url}/v1/research/health")
            assert research_health.status_code == 200
            print("✅ Research Engine health check passed")
            
            # Test 2: Create a test project
            project_data = {
                "name": "Smoke Test Project",
                "description": "Test project for deployment validation"
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-ODIN-Agent": "did:odin:deployer"
            }
            
            project_response = await client.post(
                f"{self.gateway_url}/v1/research/projects",
                json=project_data,
                headers=headers
            )
            
            if project_response.status_code == 201:
                project = project_response.json()
                print(f"✅ Project creation test passed (ID: {project['id']})")
                
                # Test 3: Get the project back
                get_response = await client.get(
                    f"{self.gateway_url}/v1/research/projects/{project['id']}",
                    headers=headers
                )
                assert get_response.status_code == 200
                print("✅ Project retrieval test passed")
                
            else:
                print(f"⚠️ Project creation failed with status {project_response.status_code}")
                print(f"Response: {project_response.text}")
        
        print("🎉 All smoke tests passed!")
    
    async def cleanup(self):
        """Clean up on deployment failure."""
        print("🧹 Cleaning up failed deployment...")
        
        try:
            subprocess.run([
                "docker-compose",
                "-f", str(self.compose_file),
                "down"
            ], cwd=self.project_root, check=True)
            print("✅ Services stopped")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
    
    def display_success(self):
        """Display successful deployment information."""
        print("\n" + "="*60)
        print("🎉 ODIN RESEARCH ENGINE DEPLOYMENT SUCCESSFUL!")
        print("="*60)
        print("Services Running:")
        print(f"  • Gateway: {self.gateway_url}")
        print(f"  • Research API: {self.gateway_url}/v1/research/*")
        print(f"  • Documentation: http://localhost:5173")
        print(f"  • Monitoring: http://localhost:3000 (Grafana)")
        print()
        print("Available APIs:")
        print("  • POST /v1/research/projects - Create project")
        print("  • POST /v1/research/byok/token - Store API key")
        print("  • POST /v1/research/experiments - Create experiment")
        print("  • POST /v1/research/runs - Execute research run")
        print("  • GET  /v1/research/health - Health check")
        print()
        print("Quick Test Commands:")
        print('  curl -X POST "http://localhost:8000/v1/research/projects" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -H "X-ODIN-Agent: did:odin:test" \\')
        print('    -d \'{"name": "My Project", "description": "Test project"}\'')
        print()
        print("To stop services:")
        print("  docker-compose -f docker-compose.research.yml down")
        print("="*60)


async def main():
    """Main deployment entry point."""
    deployer = OdinDeployer()
    return await deployer.deploy()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)
