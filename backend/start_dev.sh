#!/bin/bash

# Development server startup script for Test Generation Agent

echo "🚀 Starting Test Generation Agent Development Server"

# Set environment variables for development
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export ENVIRONMENT="development"
export DEBUG="true"
export LOG_LEVEL="INFO"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📋 Installing dependencies..."
pip install -r requirements.txt

# Check if database is running (optional)
echo "🗄️  Checking database connection..."
python -c "
import asyncio
from app.core.database import test_connection

async def check():
    try:
        await test_connection()
        print('✅ Database connection successful')
    except Exception as e:
        print(f'⚠️  Database connection failed: {e}')
        print('💡 Make sure PostgreSQL is running and configured correctly')

asyncio.run(check())
" 2>/dev/null || echo "⚠️  Could not test database connection"

# Start the FastAPI server
echo "🌐 Starting FastAPI server..."
echo "📖 API Documentation: http://localhost:8000/api/v1/docs"
echo "🔍 Health Check: http://localhost:8000/health"
echo "📊 Metrics: http://localhost:8000/health/detailed"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
