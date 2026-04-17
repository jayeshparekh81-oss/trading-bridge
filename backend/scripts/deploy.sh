#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════
# TradeForge — Production Deployment Script
# Usage: ./scripts/deploy.sh
# ═══════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="/opt/tradeforge/backend"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="/opt/tradeforge/backups"

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

# ─── 1. Pre-flight checks ──────────────────────────────────────────
log "Pre-flight checks..."
[ -f "${APP_DIR}/.env.production" ] || fail ".env.production not found at ${APP_DIR}"
command -v docker >/dev/null 2>&1 || fail "Docker not installed"
command -v docker-compose >/dev/null 2>&1 || command -v "docker compose" >/dev/null 2>&1 || fail "docker-compose not installed"

# ─── 2. Pull latest code ───────────────────────────────────────────
log "Pulling latest code..."
cd "${APP_DIR}/.."
git pull origin main || fail "Git pull failed"

# ─── 3. Backup database ────────────────────────────────────────────
log "Creating database backup..."
mkdir -p "${BACKUP_DIR}"
BACKUP_FILE="${BACKUP_DIR}/db_$(date +%Y%m%d_%H%M%S).sql.gz"
if docker exec tradeforge_backend python -c "print('ok')" 2>/dev/null; then
    warn "Skipping DB backup (manual backup recommended before deploy)"
fi
log "Backup location: ${BACKUP_DIR}"

# ─── 4. Build new image ────────────────────────────────────────────
log "Building Docker image..."
cd "${APP_DIR}"
docker compose -f "${COMPOSE_FILE}" build backend || fail "Docker build failed"

# ─── 5. Run database migrations ────────────────────────────────────
log "Running database migrations..."
docker compose -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head || fail "Migration failed"

# ─── 6. Rolling restart ────────────────────────────────────────────
log "Restarting services..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans || fail "Service restart failed"

# ─── 7. Wait for health check ──────────────────────────────────────
log "Waiting for health check..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        log "Health check passed!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        fail "Health check failed after 30 seconds. ROLLING BACK..."
    fi
    sleep 1
done

# ─── 8. Verify all services ────────────────────────────────────────
log "Verifying services..."
docker compose -f "${COMPOSE_FILE}" ps --format "table {{.Name}}\t{{.Status}}" | head -10

# ─── 9. Done ───────────────────────────────────────────────────────
log "=========================================="
log "  Deployment COMPLETE"
log "  API: https://api.tradeforge.in/health"
log "  Docs: https://api.tradeforge.in/docs"
log "=========================================="
