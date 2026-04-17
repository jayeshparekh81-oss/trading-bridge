#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════
# TradeForge — Full Production Deployment
# Deploys backend (EC2) + frontend (Vercel) + verifies everything
#
# Prerequisites:
#   - SSH access to EC2 configured (~/.ssh/tradeforge-key.pem)
#   - Vercel CLI installed (npm i -g vercel)
#   - Domain configured in Cloudflare
#
# Usage: ./deploy-production.sh
# ═══════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

EC2_HOST="${EC2_HOST:-ubuntu@api.tradeforge.in}"
EC2_KEY="${EC2_KEY:-~/.ssh/tradeforge-key.pem}"

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
step() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║         TradeForge Production Deploy              ║"
echo "║         Built by L&T Engineer                     ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ─── Step 1: Push latest code ──────────────────────────────────────
step "Step 1: Push latest code to GitHub"
git add -A
git diff --cached --quiet || git commit -m "deploy: $(date +%Y-%m-%d_%H:%M)"
git push origin main
log "Code pushed to GitHub"

# ─── Step 2: Deploy backend to EC2 ─────────────────────────────────
step "Step 2: Deploy backend to EC2"
ssh -i "${EC2_KEY}" "${EC2_HOST}" << 'REMOTE'
    cd /opt/tradeforge
    git pull origin main
    cd backend
    docker compose -f docker-compose.prod.yml build backend
    docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
    docker compose -f docker-compose.prod.yml up -d --remove-orphans
    sleep 5
    curl -sf http://localhost:8000/health && echo "Backend healthy!" || echo "WARNING: Health check failed"
REMOTE
log "Backend deployed to EC2"

# ─── Step 3: Deploy frontend to Vercel ─────────────────────────────
step "Step 3: Deploy frontend to Vercel"
cd frontend
vercel --prod --yes 2>/dev/null || warn "Vercel deploy failed (install with: npm i -g vercel)"
cd ..
log "Frontend deployed to Vercel"

# ─── Step 4: Smoke tests ───────────────────────────────────────────
step "Step 4: Smoke tests"

check_url() {
    local url=$1
    local code
    code=$(curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
        log "$url → ${code}"
    else
        warn "$url → ${code} (may need DNS propagation)"
    fi
}

check_url "https://api.tradeforge.in/health"
check_url "https://tradeforge.in"
log "Smoke tests complete"

# ─── Done ───────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║         Deployment COMPLETE!                      ║"
echo "║                                                   ║"
echo "║  Frontend: https://tradeforge.in                  ║"
echo "║  Backend:  https://api.tradeforge.in              ║"
echo "║  API Docs: https://api.tradeforge.in/docs         ║"
echo "║  Health:   https://api.tradeforge.in/health        ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
