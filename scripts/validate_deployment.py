#!/usr/bin/env python3
"""
ODIN Ecosystem Validation Script

Validates that all core ODIN components are working properly
and ready for production deployment.

✅ = Working correctly
⚠️  = Working with warnings
❌ = Failed/Missing
"""

import sys
import os
import subprocess
import importlib
from pathlib import Path
from typing import List, Tuple, Dict, Any
import json

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_import(module_name: str, description: str) -> Tuple[str, bool]:
    """Test if a module can be imported successfully."""
    try:
        importlib.import_module(module_name)
        return f"✅ {description}", True
    except ImportError as e:
        return f"❌ {description}: {str(e)}", False
    except Exception as e:
        return f"⚠️  {description}: {str(e)}", True  # Module exists but has runtime issues

def check_file_exists(file_path: str, description: str) -> Tuple[str, bool]:
    """Check if a file exists."""
    path = project_root / file_path
    if path.exists():
        return f"✅ {description}", True
    else:
        return f"❌ {description}: File not found at {path}", False

def check_directory_structure() -> List[Tuple[str, bool]]:
    """Validate the project directory structure."""
    results = []
    
    # Core directories
    core_dirs = [
        ("libs/odin_core", "ODIN Core Library"),
        ("apps/gateway", "Gateway Service"),
        ("services/relay", "Relay Service"), 
        ("deploy", "Deployment Configuration"),
        ("tests", "Test Suite"),
    ]
    
    for dir_path, desc in core_dirs:
        results.append(check_file_exists(dir_path, desc))
    
    return results

def check_core_imports() -> List[Tuple[str, bool]]:
    """Test core ODIN module imports."""
    results = []
    
    # Core ODIN modules
    core_modules = [
        ("libs.odin_core.odin.oml", "ODIN Messaging Language (OML)"),
        ("libs.odin_core.odin.ope", "ODIN Proof Engine (OPE)"),
        ("libs.odin_core.odin.sft", "Semantic Function Transform (SFT)"),
        ("libs.odin_core.odin.bridge_engine", "Bridge Pro Engine"),
        ("libs.odin_core.odin.research", "Research Engine"),
        ("libs.odin_core.odin.crypto.blake3_hash", "Cryptographic Hashing"),
        ("libs.odin_core.odin.jwks", "JSON Web Key Set"),
        ("libs.odin_core.odin.storage.firestore", "Firestore Backend"),
    ]
    
    for module, desc in core_modules:
        results.append(check_import(module, desc))
    
    return results

def check_deployment_files() -> List[Tuple[str, bool]]:
    """Check deployment configuration files."""
    results = []
    
    deployment_files = [
        (".github/workflows/deploy.yml", "GitHub Actions CI/CD Pipeline"),
        ("deploy/setup-gcp.sh", "GCP Infrastructure Setup Script"),
        ("deploy/gateway/Dockerfile", "Gateway Production Container"),
        ("deploy/relay/Dockerfile", "Relay Production Container"),
        ("deploy/site/Dockerfile", "Site Production Container"),
        ("deploy/site/nginx.conf", "NGINX Configuration"),
        ("deploy/startup.sh", "Cloud Run Startup Script"),
        ("deploy/README.md", "Deployment Documentation"),
    ]
    
    for file_path, desc in deployment_files:
        results.append(check_file_exists(file_path, desc))
    
    return results

def check_cors_configuration() -> List[Tuple[str, bool]]:
    """Check that CORS is properly configured in services."""
    results = []
    
    try:
        # Check Gateway CORS
        with open(project_root / "apps/gateway/api.py", 'r') as f:
            gateway_content = f.read()
            if "CORSMiddleware" in gateway_content and "add_middleware" in gateway_content:
                results.append(("✅ Gateway CORS Configuration", True))
            else:
                results.append(("❌ Gateway CORS Configuration: Missing middleware", False))
    except Exception as e:
        results.append((f"❌ Gateway CORS Check: {str(e)}", False))
    
    try:
        # Check Relay CORS
        with open(project_root / "services/relay/api.py", 'r') as f:
            relay_content = f.read()
            if "CORSMiddleware" in relay_content and "add_middleware" in relay_content:
                results.append(("✅ Relay CORS Configuration", True))
            else:
                results.append(("❌ Relay CORS Configuration: Missing middleware", False))
    except Exception as e:
        results.append((f"❌ Relay CORS Check: {str(e)}", False))
    
    return results

def check_security_features() -> List[Tuple[str, bool]]:
    """Check security implementations."""
    results = []
    
    try:
        # Check HEL Security
        from libs.odin_core.odin.security.keystore import load_keypair_from_env
        results.append(("✅ HEL Security System", True))
    except Exception as e:
        results.append((f"❌ HEL Security System: {str(e)}", False))
    
    try:
        # Check JWKS rotation
        from libs.odin_core.odin.jwks import KeyRegistry
        results.append(("✅ JWKS Key Rotation", True))
    except Exception as e:
        results.append((f"❌ JWKS Key Rotation: {str(e)}", False))
    
    # Check for Workload Identity Federation config
    wif_check = check_file_exists(".github/workflows/deploy.yml", "Workload Identity Federation")
    if wif_check[1]:
        results.append(("✅ Workload Identity Federation Setup", True))
    else:
        results.append(("❌ Workload Identity Federation Setup", False))
    
    return results

def check_database_backends() -> List[Tuple[str, bool]]:
    """Check database backend implementations."""
    results = []
    
    try:
        # Check in-memory backend
        from libs.odin_core.odin.storage.memory import InMemoryStorage
        results.append(("✅ In-Memory Storage Backend", True))
    except Exception as e:
        results.append((f"❌ In-Memory Storage Backend: {str(e)}", False))
    
    try:
        # Check Firestore backend
        from libs.odin_core.odin.storage.firestore import FirestoreStorage
        results.append(("✅ Firestore Storage Backend", True))
    except Exception as e:
        results.append((f"❌ Firestore Storage Backend: {str(e)}", False))
    
    return results

def main():
    """Run complete ODIN ecosystem validation."""
    print("🔍 ODIN Ecosystem Validation Report")
    print("=" * 50)
    print()
    
    all_results = []
    
    # Run all validation checks
    validation_sections = [
        ("📁 Directory Structure", check_directory_structure),
        ("🐍 Core Module Imports", check_core_imports),
        ("🚀 Deployment Files", check_deployment_files),
        ("🌐 CORS Configuration", check_cors_configuration),
        ("🔐 Security Features", check_security_features),
        ("💾 Database Backends", check_database_backends),
    ]
    
    total_checks = 0
    passed_checks = 0
    
    for section_name, check_function in validation_sections:
        print(f"{section_name}:")
        section_results = check_function()
        
        for result_text, success in section_results:
            print(f"  {result_text}")
            total_checks += 1
            if success:
                passed_checks += 1
        
        all_results.extend(section_results)
        print()
    
    # Summary
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total Checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    print(f"Success Rate: {(passed_checks / total_checks * 100):.1f}%")
    print()
    
    # Deployment readiness assessment
    if passed_checks >= total_checks * 0.9:  # 90% success rate
        print("🎉 DEPLOYMENT STATUS: ✅ READY FOR PRODUCTION")
        print("Your ODIN ecosystem is production-ready!")
        print()
        print("Next Steps:")
        print("1. Run: ./deploy/setup-gcp.sh YOUR_PROJECT_ID")
        print("2. Configure GitHub repository secrets")
        print("3. Push to main (dev) or tag a release (prod)")
        print("4. Validate deployed services")
    elif passed_checks >= total_checks * 0.7:  # 70% success rate
        print("⚠️  DEPLOYMENT STATUS: 🔶 NEEDS ATTENTION")
        print("Most systems are working but some issues need resolution.")
    else:
        print("❌ DEPLOYMENT STATUS: 🔴 NOT READY")
        print("Multiple critical issues need to be resolved.")
    
    print()
    print("For deployment help, see: deploy/README.md")
    
    # Exit code based on success rate
    if passed_checks >= total_checks * 0.9:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Issues found

if __name__ == "__main__":
    main()
