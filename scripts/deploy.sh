#!/bin/bash
# ODIN Research Engine - Deployment Script
# Builds, tests, and deploys the complete Research Engine

set -e

echo "🚀 Starting ODIN Research Engine deployment..."

# Configuration
DOCKER_TAG=${DOCKER_TAG:-"odin-research:latest"}
ENVIRONMENT=${ENVIRONMENT:-"development"}
RUN_TESTS=${RUN_TESTS:-"true"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Environment validation
log_info "Validating environment..."

if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

log_success "Environment validation passed"

# Step 2: Build application
log_info "Building ODIN Research Engine..."

docker build -f Dockerfile.research -t $DOCKER_TAG .
if [ $? -eq 0 ]; then
    log_success "Docker build completed"
else
    log_error "Docker build failed"
    exit 1
fi

# Step 3: Run tests
if [ "$RUN_TESTS" = "true" ]; then
    log_info "Running test suite..."
    
    # Create test network if it doesn't exist
    docker network create odin-test-network 2>/dev/null || true
    
    # Start test dependencies
    docker-compose -f docker-compose.research.yml up -d postgres redis
    
    # Wait for dependencies to be ready
    log_info "Waiting for dependencies to be ready..."
    sleep 10
    
    # Run tests in container
    docker run --rm \
        --network odin-test-network \
        -e DATABASE_URL=postgresql://odin:odin@postgres:5432/odin_research \
        -e REDIS_URL=redis://redis:6379/0 \
        -v $(pwd):/app \
        $DOCKER_TAG \
        python -m pytest tests/test_research_engine.py -v
    
    if [ $? -eq 0 ]; then
        log_success "All tests passed"
    else
        log_error "Tests failed"
        docker-compose -f docker-compose.research.yml down
        exit 1
    fi
    
    # Clean up test dependencies
    docker-compose -f docker-compose.research.yml down
else
    log_warning "Skipping tests (RUN_TESTS=false)"
fi

# Step 4: Deploy based on environment
log_info "Deploying to $ENVIRONMENT environment..."

case $ENVIRONMENT in
    "development")
        log_info "Starting development environment..."
        docker-compose -f docker-compose.research.yml up -d
        
        # Wait for services to be ready
        log_info "Waiting for services to start..."
        sleep 15
        
        # Health check
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Gateway is healthy"
        else
            log_error "Gateway health check failed"
            exit 1
        fi
        
        if curl -f http://localhost:8080/v1/health > /dev/null 2>&1; then
            log_success "Research Engine is healthy"
        else
            log_error "Research Engine health check failed"
            exit 1
        fi
        
        log_success "Development environment deployed successfully!"
        echo ""
        echo "🌐 Services available at:"
        echo "   Gateway: http://localhost:8080"
        echo "   Research Engine: http://localhost:8080/v1/health"
        echo "   Documentation: http://localhost:3000"
        echo "   Prometheus: http://localhost:9090"
        echo "   Grafana: http://localhost:3001 (admin/odin)"
        echo "   IPFS: http://localhost:8081"
        ;;
        
    "staging")
        log_info "Deploying to staging..."
        # Add staging deployment logic here
        # kubectl apply -f k8s/staging/
        log_warning "Staging deployment not implemented yet"
        ;;
        
    "production")
        log_info "Deploying to production..."
        # Add production deployment logic here
        # kubectl apply -f k8s/production/
        log_warning "Production deployment not implemented yet"
        ;;
        
    *)
        log_error "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

# Step 5: Post-deployment verification
log_info "Running post-deployment verification..."

# Test Research Engine endpoints
test_endpoint() {
    local url=$1
    local description=$2
    
    if curl -f $url > /dev/null 2>&1; then
        log_success "$description: OK"
        return 0
    else
        log_error "$description: FAILED"
        return 1
    fi
}

GATEWAY_URL="http://localhost:8080"

test_endpoint "$GATEWAY_URL/health" "Gateway health"
test_endpoint "$GATEWAY_URL/v1/health" "Research Engine health"
test_endpoint "$GATEWAY_URL/metrics" "Metrics endpoint"

# Test Research Engine project creation (requires valid headers)
log_info "Testing Research Engine project creation..."
PROJECT_RESPONSE=$(curl -s -X POST "$GATEWAY_URL/v1/projects" \
    -H "Content-Type: application/json" \
    -H "X-ODIN-Agent: did:odin:deploy-test" \
    -d '{"name": "Deploy Test Project", "description": "Test project created during deployment"}')

if echo "$PROJECT_RESPONSE" | grep -q '"id"'; then
    log_success "Research Engine project creation: OK"
    PROJECT_ID=$(echo "$PROJECT_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    log_info "Created test project: $PROJECT_ID"
else
    log_error "Research Engine project creation: FAILED"
    log_error "Response: $PROJECT_RESPONSE"
fi

log_success "🎉 ODIN Research Engine deployment completed successfully!"

echo ""
echo "📋 Deployment Summary:"
echo "   Environment: $ENVIRONMENT"
echo "   Docker Tag: $DOCKER_TAG"
echo "   Tests Run: $RUN_TESTS"
echo "   Gateway URL: $GATEWAY_URL"
echo ""
echo "🔧 Next Steps:"
echo "   1. Visit the documentation at http://localhost:3000/research"
echo "   2. Try the Research Engine in the playground"
echo "   3. Monitor metrics at http://localhost:9090"
echo "   4. View logs: docker-compose -f docker-compose.research.yml logs -f"
echo ""
echo "🛑 To stop services: docker-compose -f docker-compose.research.yml down"
