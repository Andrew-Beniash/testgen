# Test Generation Agent Backend

Python backend service for the Test Generation Agent with Quality Assurance.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker and Docker Compose (optional)

### Development Setup

1. **Clone the repository and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run with Docker Compose (Recommended):**
   ```bash
   docker-compose up -d
   ```

6. **Or run locally:**
   ```bash
   # Start database and Redis first
   python -m app.main
   ```

### API Documentation

Once running, visit:
- API Documentation: http://localhost:8000/api/v1/docs
- Alternative Docs: http://localhost:8000/api/v1/redoc
- Health Check: http://localhost:8000/health

### Environment Variables

Key environment variables (see `.env.example` for full list):

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key for AI generation
- `AZURE_DEVOPS_*`: Azure DevOps integration settings
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Project Structure

```
backend/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── core/             # Core configuration
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   └── utils/            # Utilities
├── tests/                # Test files
├── docker-compose.yml    # Docker services
└── requirements.txt      # Python dependencies
```

### Quality Features

This backend implements:
- Multi-layer test case validation
- Ground truth benchmarking
- Continuous learning from QA feedback
- Quality-assured AI generation
- Comprehensive analytics and reporting

### Development

1. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

2. **Code formatting:**
   ```bash
   black app/
   isort app/
   ```

3. **Type checking:**
   ```bash
   mypy app/
   ```

### Docker Services

The docker-compose setup includes:
- **PostgreSQL**: Primary database
- **Redis**: Caching and session storage
- **Qdrant**: Vector database for similarity search
- **Backend**: FastAPI application
- **Nginx**: Reverse proxy (production profile)
- **Prometheus/Grafana**: Monitoring (monitoring profile)

### Monitoring

Access monitoring tools:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

### Production Deployment

For production deployment:

1. **Update environment variables for production**
2. **Use production docker-compose profile:**
   ```bash
   docker-compose --profile production up -d
   ```
3. **Set up SSL certificates in the ssl/ directory**
4. **Configure proper secrets management**

### Support

For issues and questions, refer to the project documentation or create an issue in the repository.
