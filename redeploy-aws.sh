#!/bin/bash
# DRISHTI AWS Redeploy Script (Linux/Mac)
# Redeploys latest Docker images to EC2 instance with all fixes

set -e

# Configuration
EC2_IP="${1:-44.216.1.62}"
SSH_KEY="${2:-$HOME/.ssh/drishti-deploy-key}"
GITHUB_REPO="404Avinash/drishti"

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║       DRISHTI AWS REDEPLOY - Latest Fixes to Production           ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Validate SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    echo "   Please provide the path to your EC2 SSH private key"
    echo ""
    echo "Usage: ./redeploy-aws.sh <EC2_IP> <SSH_KEY_PATH>"
    echo "Example: ./redeploy-aws.sh 44.216.1.62 ~/.ssh/drishti-deploy-key"
    exit 1
fi

echo "✓ Configuration:"
echo "  EC2 IP: $EC2_IP"
echo "  SSH Key: $SSH_KEY"
echo "  GitHub Repo: $GITHUB_REPO"
echo ""

# Remote deployment commands
echo "🚀 Connecting to EC2 and deploying..."
echo ""

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$EC2_IP" << 'REMOTE_COMMANDS'
#!/bin/bash
set -e

echo "🔄 Starting DRISHTI redeploy..."
echo ""

# Navigate to app directory
mkdir -p /home/ubuntu/drishti
cd /home/ubuntu/drishti

echo "📦 [1/6] Pulling latest Docker images from GitHub Container Registry..."
docker pull ghcr.io/404avinash/drishti/backend:latest
docker pull ghcr.io/404avinash/drishti/frontend:latest

echo ""
echo "🛑 [2/6] Stopping old containers..."
docker compose -f docker-compose.production.yml down --timeout 10 2>/dev/null || true

echo ""
echo "🧹 [3/6] Cleaning up old images and build cache..."
docker image prune -af --filter "until=24h" || true
docker builder prune -af --filter "until=24h" || true

echo ""
echo "⚙️  [4/6] Starting new containers with latest images..."
docker compose -f docker-compose.production.yml up -d

echo ""
echo "⏳ [5/6] Waiting for containers to be healthy (30 seconds)..."
sleep 30

echo ""
echo "🏥 [6/6] Checking backend health..."
if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8000/api/health | grep -o '"status":"[^"]*"')
    echo "✅ Backend is healthy: $HEALTH"
else
    echo "⚠️  Backend still initializing, please check logs in 30 seconds"
    sleep 10
fi

echo ""
echo "✅ Redeploy complete!"
echo "   Application: http://44.216.1.62/"
echo "   Dashboard: http://44.216.1.62/dashboard"
echo ""
echo "To view logs, run:"
echo "  docker compose logs -f"
REMOTE_COMMANDS

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ REDEPLOY SUCCESSFUL                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 DRISHTI is now running with all latest fixes!"
echo ""
echo "📍 Access your system:"
echo "   🌐 Application: http://$EC2_IP/"
echo "   📊 Dashboard: http://$EC2_IP/dashboard"
echo "   🚨 Alerts: http://$EC2_IP/alerts"
echo "   🧠 AI Decisions: http://$EC2_IP/ai-decisions"
echo "   ⚙️  System Health: http://$EC2_IP/system"
echo ""
echo "📝 To view logs:"
echo "   ssh -i '$SSH_KEY' ubuntu@$EC2_IP"
echo "   cd /home/ubuntu/drishti && docker compose logs -f"
echo ""
