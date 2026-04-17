# Deployment Guide

## Local Development

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### Quick Start

```bash
# Clone
git clone https://github.com/jayeshparekh81-oss/trading-bridge.git
cd trading-bridge

# Start infrastructure
docker-compose up -d postgres redis

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env — set ENCRYPTION_KEY and JWT_SECRET

# Run migrations
alembic upgrade head

# Seed dev data
python -m scripts.seed_dev

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Full Docker Stack

```bash
# Start everything (PostgreSQL + Redis + API + Celery)
docker-compose up

# Or in background
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

Services:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Running Tests

```bash
cd backend
source .venv/bin/activate
pytest                          # Full suite
pytest -x                       # Stop on first failure
pytest tests/test_auth_service.py  # Single file
pytest -k "test_login"          # By name
pytest --cov=app --cov-report=html  # With coverage
```

## Production Deployment (AWS EC2)

### 1. Instance Setup

```bash
# Ubuntu 22.04 LTS, t3.medium or larger
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  docker.io docker-compose-plugin
```

### 2. Application

```bash
# Clone and configure
git clone <repo> /opt/trading-bridge
cd /opt/trading-bridge/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Production .env
cp .env.example .env
# Set: ENVIRONMENT=production, real keys, DB URL, Redis URL
```

### 3. Database

```bash
# RDS PostgreSQL (recommended) or local
alembic upgrade head
```

### 4. Process Management (systemd)

```ini
# /etc/systemd/system/trading-bridge.service
[Unit]
Description=Trading Bridge API
After=network.target

[Service]
Type=exec
User=www-data
WorkingDirectory=/opt/trading-bridge/backend
Environment=PATH=/opt/trading-bridge/backend/.venv/bin
ExecStart=/opt/trading-bridge/backend/.venv/bin/uvicorn \
  app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 5. Nginx + SSL

```nginx
server {
    listen 443 ssl http2;
    server_name api.tradingbridge.in;

    ssl_certificate /etc/letsencrypt/live/api.tradingbridge.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.tradingbridge.in/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo certbot --nginx -d api.tradingbridge.in
```

### 6. Celery Workers

```ini
# /etc/systemd/system/trading-bridge-worker.service
[Unit]
Description=Trading Bridge Celery Worker

[Service]
Type=exec
User=www-data
WorkingDirectory=/opt/trading-bridge/backend
ExecStart=/opt/trading-bridge/backend/.venv/bin/celery \
  -A app.tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7. Monitoring

- **Health check**: `GET /health/ready` (load balancer target)
- **Prometheus**: Metrics at `/metrics` (when enabled)
- **Logs**: JSON structured via structlog → CloudWatch / ELK

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | Yes | development | development/staging/production |
| `ENCRYPTION_KEY` | Yes | - | Fernet key for credential encryption |
| `JWT_SECRET` | Yes | - | HS256 signing key (min 32 chars) |
| `DATABASE_URL` | Yes | localhost | PostgreSQL async URL |
| `REDIS_URL` | Yes | localhost:6379 | Redis connection URL |
| `AWS_SES_REGION` | No | ap-south-1 | AWS SES region |
| `AWS_ACCESS_KEY_ID` | No | - | AWS credentials for SES |
| `AWS_SECRET_ACCESS_KEY` | No | - | AWS credentials for SES |
| `FROM_EMAIL` | No | alerts@tradingbridge.in | Sender email |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot API token |
| `FYERS_APP_ID` | No | - | Platform-level Fyers app ID |
| `CELERY_BROKER_URL` | No | redis://localhost:6379/1 | Celery broker |
