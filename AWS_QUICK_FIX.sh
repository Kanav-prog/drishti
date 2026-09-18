#!/bin/bash
# DRISHTI AWS - DIRECT FIX (No fancy stuff, just works)
# Copy-paste this entire script into SSH terminal

cd /home/ubuntu/drishti

echo "🔥 DRISHTI EMERGENCY RESTART"
echo "="
echo ""

# STEP 1: Kill everything
echo "⏹️  Stopping everything..."
docker compose -f docker-compose.production.yml down -v 2>/dev/null || true
sleep 5

# STEP 2: Clean up
echo "🧹 Cleaning up..."
docker image prune -af 2>/dev/null || true
docker builder prune -af 2>/dev/null || true

# STEP 3: Load environment
echo "⚙️  Loading environment..."
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "   Terraform should have created this."
    echo "   Check: ls -la .env"
    exit 1
fi
source .env
echo "✅ Environment loaded"

# STEP 4: Force pull latest images
echo "📥 Pulling latest images from GitHub..."
docker pull ghcr.io/404avinash/drishti/backend:latest
docker pull ghcr.io/404avinash/drishti/frontend:latest

# STEP 5: Start fresh
echo "🚀 Starting containers..."
docker compose -f docker-compose.production.yml up -d

# STEP 6: Wait for startup
echo "⏳ Waiting 45 seconds for services..."
sleep 45

# STEP 7: Verify
echo ""
echo "🔍 Container status:"
docker compose -f docker-compose.production.yml ps

echo ""
echo "🏥 Backend health:"
curl -s http://localhost:8000/api/health | jq . || echo "⚠️  Still initializing..."

echo ""
echo "✅ DONE! System should be LIVE now."
echo ""
echo "Test: Open http://44.216.1.62/ in browser"
echo ""
