# Production Deployment Guide

Complete step-by-step guide to deploy TradeForge to production.

## Architecture

```
Users → Cloudflare CDN → Vercel (Frontend)
                       → EC2 (Backend API)
                            ├── FastAPI (4 workers)
                            ├── Celery Worker
                            ├── Celery Beat
                            ├── Redis (local)
                            └── Nginx (SSL)
                       → RDS PostgreSQL (Database)
```

## Prerequisites

- AWS Account (create at aws.amazon.com)
- Domain name (tradeforge.in — ~₹600/year from GoDaddy/Namecheap)
- Cloudflare account (free at cloudflare.com)
- Vercel account (free at vercel.com)
- GitHub repository (already set up)

---

## Step 1: AWS EC2 Instance

### 1.1 Launch Instance

1. Go to AWS Console → EC2 → Launch Instance
2. Settings:
   - **Name**: tradeforge-prod
   - **AMI**: Ubuntu 22.04 LTS
   - **Type**: t3.small (₹1,500/mo) or t2.micro (free tier)
   - **Key pair**: Create new → "tradeforge-key" → Download `.pem` file
   - **Security Group**: Create new with rules:
     - SSH (22) — Your IP only
     - HTTP (80) — Anywhere
     - HTTPS (443) — Anywhere
   - **Storage**: 30 GB gp3

3. Click **Launch Instance**

### 1.2 Elastic IP

1. EC2 → Elastic IPs → Allocate
2. Associate with your instance
3. Note the IP: `___.___.___.__`

### 1.3 Connect & Setup

```bash
# Save key file
chmod 400 ~/.ssh/tradeforge-key.pem

# Connect
ssh -i ~/.ssh/tradeforge-key.pem ubuntu@YOUR_ELASTIC_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Install Certbot (SSL)
sudo apt install -y certbot

# Install Git
sudo apt install -y git

# Firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Logout and reconnect for Docker group
exit
```

### 1.4 Deploy Code

```bash
ssh -i ~/.ssh/tradeforge-key.pem ubuntu@YOUR_ELASTIC_IP

# Clone repo
sudo mkdir -p /opt/tradeforge
sudo chown ubuntu:ubuntu /opt/tradeforge
cd /opt/tradeforge
git clone https://github.com/jayeshparekh81-oss/trading-bridge.git .

# Create production env
cd backend
cp .env.production.example .env.production
nano .env.production   # Fill in all values
```

**IMPORTANT**: Generate fresh keys for production:
```bash
# Fernet key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT secret
openssl rand -hex 32
```

---

## Step 2: AWS RDS PostgreSQL

1. AWS Console → RDS → Create Database
2. Settings:
   - **Engine**: PostgreSQL 16
   - **Template**: Free tier
   - **Instance**: db.t3.micro
   - **Storage**: 20 GB, GP2
   - **DB name**: tradeforge
   - **Master username**: tradeforge_admin
   - **Password**: (generate strong password)
   - **VPC**: Same as EC2
   - **Public access**: No
   - **Security Group**: Create new — allow PostgreSQL (5432) from EC2 security group only
3. Note the **Endpoint**: `tradeforge.xxxxx.ap-south-1.rds.amazonaws.com`
4. Update `.env.production`:
   ```
   DATABASE_URL=postgresql+asyncpg://tradeforge_admin:PASSWORD@ENDPOINT:5432/tradeforge
   ```

---

## Step 3: SSL Certificate

```bash
ssh -i ~/.ssh/tradeforge-key.pem ubuntu@YOUR_ELASTIC_IP

# Get SSL certificate (before starting Nginx)
sudo certbot certonly --standalone -d api.tradeforge.in

# Auto-renewal cron
sudo certbot renew --dry-run
```

---

## Step 4: Start Backend

```bash
cd /opt/tradeforge/backend

# Build and start
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d

# Verify
curl http://localhost:8000/health
docker compose -f docker-compose.prod.yml ps

# Seed admin user
docker compose -f docker-compose.prod.yml run --rm backend python -m scripts.seed_dev
```

---

## Step 5: Frontend on Vercel

```bash
# On your local machine
cd ~/projects/trading-bridge/frontend

# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel --prod

# Set environment variable in Vercel dashboard:
# Settings → Environment Variables
# NEXT_PUBLIC_API_URL = https://api.tradeforge.in
```

---

## Step 6: Cloudflare DNS

1. Sign up at cloudflare.com (free)
2. Add site: tradeforge.in
3. Update nameservers at your domain registrar
4. DNS Records:
   - `A` `@` → Vercel IP (from Vercel dashboard)
   - `CNAME` `www` → `tradeforge.in`
   - `A` `api` → Your EC2 Elastic IP
5. SSL: Full (Strict)
6. Always Use HTTPS: ON

---

## Step 7: Verify Everything

```bash
# Backend health
curl https://api.tradeforge.in/health

# Frontend
curl -I https://tradeforge.in

# API docs
# Open: https://api.tradeforge.in/docs

# Test flow:
# 1. Open https://tradeforge.in
# 2. Click Register
# 3. Create account
# 4. Login → Dashboard loads
```

---

## Subsequent Deployments

```bash
# From your local machine:
./deploy-production.sh

# Or manually:
# Backend:
ssh -i ~/.ssh/tradeforge-key.pem ubuntu@YOUR_IP
cd /opt/tradeforge && git pull && cd backend
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d

# Frontend:
cd frontend && vercel --prod
```

---

## Rollback

```bash
# Backend: revert to previous image
docker compose -f docker-compose.prod.yml down
git checkout HEAD~1
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Database: restore from RDS snapshot
# AWS Console → RDS → Snapshots → Restore
```

---

## Monitoring Setup

### UptimeRobot (Free)
1. Sign up at uptimerobot.com
2. Add monitors:
   - `https://tradeforge.in` (5 min interval)
   - `https://api.tradeforge.in/health` (5 min interval)
3. Set up email + SMS alerts

### Log Access
```bash
# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# View Nginx logs
docker compose -f docker-compose.prod.yml logs -f nginx

# View all
docker compose -f docker-compose.prod.yml logs -f
```
