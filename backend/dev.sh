#!/bin/bash

# Test Generation Agent Development Script
# This script helps with common development tasks

set -e

PROJECT_DIR="/Users/andreibeniash/Documents/test_auto/testgen/backend"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    log_info "Docker is running"
}

# Function to setup environment
setup_env() {
    if [ ! -f ".env" ]; then
        log_info "Creating .env file from template"
        cp .env.example .env
        log_warn "Please edit .env file with your configuration"
    else
        log_info ".env file already exists"
    fi
}

# Function to start services
start_services() {
    log_info "Starting all services with Docker Compose"
    docker-compose up -d --build
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    if docker-compose ps | grep -q "unhealthy"; then
        log_error "Some services are unhealthy. Check logs with: docker-compose logs"
        docker-compose ps
        exit 1
    fi
    
    log_info "All services are running!"
    docker-compose ps
}

# Function to stop services
stop_services() {
    log_info "Stopping all services"
    docker-compose down
}

# Function to view logs
view_logs() {
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Function to clean up
cleanup() {
    log_info "Cleaning up Docker resources"
    docker-compose down --volumes --remove-orphans
    docker system prune -f
}

# Function to run tests
run_tests() {
    log_info "Running tests in backend container"
    docker-compose exec backend pytest tests/ -v
}

# Function to check API health
check_health() {
    log_info "Checking API health"
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_info "API is healthy! ✅"
        curl -s http://localhost:8000/health | python -m json.tool
    else
        log_error "API is not responding"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "Test Generation Agent Development Helper"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     - Setup environment and configuration"
    echo "  start     - Start all services"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  logs      - View logs (optionally specify service name)"
    echo "  health    - Check API health"
    echo "  test      - Run tests"
    echo "  clean     - Clean up Docker resources"
    echo "  shell     - Open shell in backend container"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs backend"
    echo "  $0 health"
}

# Main script logic
case "${1:-help}" in
    setup)
        check_docker
        setup_env
        ;;
    start)
        check_docker
        setup_env
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        check_docker
        log_info "Restarting services"
        docker-compose restart
        ;;
    logs)
        view_logs "$2"
        ;;
    health)
        check_health
        ;;
    test)
        run_tests
        ;;
    clean)
        cleanup
        ;;
    shell)
        docker-compose exec backend /bin/bash
        ;;
    help|*)
        show_help
        ;;
esac
