# ODIN Research Engine - Quick Deployment Script
# Run this to deploy the complete Research Engine stack

Write-Host "🚀 ODIN Research Engine - Quick Deployment" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

# Check if Docker is running
Write-Host "📋 Checking Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Run integration tests first
Write-Host "`n🧪 Running integration tests..." -ForegroundColor Yellow
python scripts\test_integration.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Integration tests failed. Please fix issues before deployment." -ForegroundColor Red
    exit 1
}

# Deploy services
Write-Host "`n🐳 Deploying services..." -ForegroundColor Yellow
python scripts\deploy_research_engine.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n🎉 Deployment completed successfully!" -ForegroundColor Green
    Write-Host "Access the Research Engine at: http://localhost:8000/v1/research/health" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Deployment failed. Check logs above." -ForegroundColor Red
    exit 1
}
