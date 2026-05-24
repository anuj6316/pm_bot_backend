---
title: Pm Bot Backend
emoji: 🐠
colorFrom: yellow
colorTo: blue
sdk: docker
pinned: false
short_description: Autonomous PM Bot project
---

# PM Bot Backend

An autonomous project management bot built with Django, Celery, and modern AI/LLM tools. This project provides intelligent assistance for project management tasks through a RESTful API and real-time communication.

## Features

- 🤖 **AI-Powered Assistant**: Leverages LangChain, LangGraph, and LiteLLM for intelligent task management
- 📦 **Django Backend**: Robust REST API built with Django Rest Framework
- ⚡ **Async Task Processing**: Celery workers for background task execution
- 🔐 **Authentication**: JWT-based authentication system
- 🔄 **Real-time Updates**: WebSocket support via Daphne ASGI server
- 🗄️ **Database**: PostgreSQL support with psycopg
- 💾 **Caching & Messaging**: Redis for caching and message brokering
- 📊 **Monitoring**: Langfuse integration for LLM observability

## Tech Stack

- **Backend Framework**: Django 6.0+
- **API**: Django Rest Framework
- **Task Queue**: Celery 5.6+
- **Message Broker**: Redis
- **AI/LLM**: LangChain, LangGraph, LiteLLM, SmolAgents
- **Database**: PostgreSQL
- **Authentication**: djangorestframework-simplejwt
- **Deployment**: Docker, Docker Compose

## Prerequisites

- Python 3.14+
- Docker & Docker Compose (for containerized deployment)
- Redis (for local development without Docker)
- PostgreSQL (for local development without Docker)

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pm-bot-backend
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Django Admin: http://localhost:8002/admin
   - API: http://localhost:8002/api/

### Local Development

1. **Install dependencies**
   ```bash
   uv install
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

4. **Start Redis** (if not using Docker)
   ```bash
   redis-server
   ```

5. **Run the development server**
   ```bash
   python manage.py runserver
   ```

6. **Start Celery worker**
   ```bash
   celery -A backend worker --loglevel=info
   ```

7. **Start Celery beat** (for scheduled tasks)
   ```bash
   celery -A backend beat --loglevel=info
   ```

## Project Structure

```
pm-bot-backend/
├── backend/                 # Django backend application
│   ├── agent/              # AI agent implementations
│   ├── authentication/     # Authentication & authorization
│   ├── chat/               # Chat functionality
│   ├── integrations/       # Third-party integrations
│   └── tests/              # Test suite
├── cli/                    # Command-line interface
├── deep_agent/             # Deep agent implementations
├── plane_client/           # Plane API client
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile             # Docker image configuration
├── supervisord.conf       # Supervisor process manager config
├── pyproject.toml         # Python project configuration
└── requirements.txt       # Python dependencies
```

## Configuration

### Environment Variables

Key environment variables to configure in `.env`:

- `DATABASE_URL`: PostgreSQL database connection string
- `REDIS_HOST`: Redis server hostname
- `CELERY_BROKER_URL`: Celery broker URL (Redis)
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode flag
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `LLM_API_KEY`: API key for LLM provider
- `LANGFUSE_PUBLIC_KEY`: Langfuse public key for monitoring
- `LANGFUSE_SECRET_KEY`: Langfuse secret key for monitoring

## API & Admin Documentation

You can access the backend interfaces and API documentation directly using the URLs below.

### 🌐 Hugging Face Spaces (Live Production)

| Service / Interface | URL | Description |
| :--- | :--- | :--- |
| **🛡️ Django Admin** | [https://anuj6316-pm-bot-backend.hf.space/admin/](https://anuj6316-pm-bot-backend.hf.space/admin/) | Manage models, sessions, and authentication keys |
| **📖 Swagger UI Docs** | [https://anuj6316-pm-bot-backend.hf.space/api/v1/docs/](https://anuj6316-pm-bot-backend.hf.space/api/v1/docs/) | Interactive OpenAPI documentation for all endpoints |
| **📕 Redoc UI Docs** | [https://anuj6316-pm-bot-backend.hf.space/api/v1/redoc/](https://anuj6316-pm-bot-backend.hf.space/api/v1/redoc/) | Clean, documentation-focused API reference |
| **📡 Browsable API** | [https://anuj6316-pm-bot-backend.hf.space/api/v1/](https://anuj6316-pm-bot-backend.hf.space/api/v1/) | DRF browsable API root |
| **📄 OpenAPI Schema** | [https://anuj6316-pm-bot-backend.hf.space/api/v1/schema/](https://anuj6316-pm-bot-backend.hf.space/api/v1/schema/) | Raw OpenAPI 3.0 specification (JSON) |

---

### 💻 Local Development

*Default local port is `8002` if running via Docker Compose, or `8000` if running `manage.py runserver` directly.*

| Service / Interface | Local Docker URL (`8002`) | Local Dev Server URL (`8000`) |
| :--- | :--- | :--- |
| **🛡️ Django Admin** | [http://localhost:8002/admin/](http://localhost:8002/admin/) | [http://localhost:8000/admin/](http://localhost:8000/admin/) |
| **📖 Swagger UI Docs** | [http://localhost:8002/api/v1/docs/](http://localhost:8002/api/v1/docs/) | [http://localhost:8000/api/v1/docs/](http://localhost:8000/api/v1/docs/) |
| **📕 Redoc UI Docs** | [http://localhost:8002/api/v1/redoc/](http://localhost:8002/api/v1/redoc/) | [http://localhost:8000/api/v1/redoc/](http://localhost:8000/api/v1/redoc/) |
| **📡 Browsable API** | [http://localhost:8002/api/v1/](http://localhost:8002/api/v1/) | [http://localhost:8000/api/v1/](http://localhost:8000/api/v1/) |
| **📄 OpenAPI Schema** | [http://localhost:8002/api/v1/schema/](http://localhost:8002/api/v1/schema/) | [http://localhost:8000/api/v1/schema/](http://localhost:8000/api/v1/schema/) |

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend

# Run specific test file
pytest backend/tests/test_file.py
```

## Deployment

### Hugging Face Spaces

This project is configured for deployment on Hugging Face Spaces. The GitHub Actions workflow automatically syncs pushes to the `main` branch with the Hugging Face Space.

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t pm-bot-backend .
   ```

2. Run the container:
   ```bash
   docker run -p 7860:7860 --env-file .env pm-bot-backend
   ```

## Development

### Code Style

This project uses standard Python conventions. Make sure to format your code before committing.

### Running Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Creating Superuser

```bash
python manage.py createsuperuser
```

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   - Ensure Redis is running: `redis-cli ping`
   - Check `REDIS_HOST` and `CELERY_BROKER_URL` in `.env`

2. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check `DATABASE_URL` in `.env`

3. **Celery Worker Not Starting**
   - Ensure Redis is accessible
   - Check Celery logs for detailed error messages

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please open an issue on the GitHub repository.
