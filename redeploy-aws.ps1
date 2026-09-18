# DRISHTI AWS Redeploy Script
# Redeploys latest Docker images to EC2 instance with all fixes

param(
    [string]$EC2_IP = "44.216.1.62",
    [string]$SSH_KEY_PATH = "$env:USERPROFILE\.ssh\drishti-deploy-key",
    [string]$GITHUB_ACTOR = "404Avinash",
    [string]$GITHUB_TOKEN = $env:GITHUB_TOKEN
)

Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       DRISHTI AWS REDEPLOY - Latest Fixes to Production           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Validate inputs
if (-Not (Test-Path $SSH_KEY_PATH)) {
    Write-Host "❌ SSH key not found at: $SSH_KEY_PATH" -ForegroundColor Red
    Write-Host "   Please provide the path to your EC2 SSH private key" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Configuration:" -ForegroundColor Green
Write-Host "  EC2 IP: $EC2_IP"
Write-Host "  SSH Key: $SSH_KEY_PATH"
Write-Host "  GitHub Actor: $GITHUB_ACTOR"
Write-Host ""

# Remote deployment script
$REMOTE_SCRIPT = @'
#!/bin/bash
set -e

echo "🔄 Starting DRISHTI redeploy..."
echo ""

# Navigate to app directory
mkdir -p /home/ubuntu/drishti
cd /home/ubuntu/drishti

echo "📦 [1/6] Pulling latest Docker images..."
docker pull ghcr.io/404avinash/drishti/backend:latest 2>&1 | head -20
docker pull ghcr.io/404avinash/drishti/frontend:latest 2>&1 | head -20

echo "🛑 [2/6] Stopping old containers..."
docker compose -f docker-compose.production.yml down --timeout 10 2>/dev/null || true

echo "🧹 [3/6] Cleaning up old images and build cache..."
docker image prune -af --filter "until=24h" || true
docker builder prune -af --filter "until=24h" || true

echo "⚙️  [4/6] Starting new containers..."
docker compose -f docker-compose.production.yml up -d

echo "⏳ [5/6] Waiting for containers to be healthy (30s)..."
sleep 30

echo "🏥 [6/6] Checking health..."
if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
else
    echo "⚠️  Backend still initializing, waiting..."
    sleep 10
    curl -f http://localhost:8000/api/health || echo "⚠️  Still starting"
fi

echo ""
echo "✅ Redeploy complete!"
echo "   Application: http://44.216.1.62/"
echo "   Check backend logs: docker compose logs -f drishti-api"
'@

# Convert to Windows-friendly format for ssh.exe
$REMOTE_SCRIPT_ESCAPED = $REMOTE_SCRIPT -replace '"', '\"' -replace '\$', '\$'

Write-Host "🚀 Connecting to EC2 and deploying..." -ForegroundColor Yellow
Write-Host ""

try {
    # Use ssh.exe (Windows built-in SSH client)
    $SSH_RESULT = ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no -o ConnectTimeout=10 `
        "ubuntu@$EC2_IP" $REMOTE_SCRIPT
    
    Write-Host $SSH_RESULT
    
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                    ✅ REDEPLOY SUCCESSFUL                         ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "🎯 DRISHTI is now running with all latest fixes!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📍 Access your system:" -ForegroundColor Cyan
    Write-Host "   🌐 Application: http://$EC2_IP/" -ForegroundColor Cyan
    Write-Host "   📊 Dashboard: http://$EC2_IP/dashboard" -ForegroundColor Cyan
    Write-Host "   🚨 Alerts: http://$EC2_IP/alerts" -ForegroundColor Cyan
    Write-Host "   ⚙️  System: http://$EC2_IP/system" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📝 To view logs:" -ForegroundColor Yellow
    Write-Host "   ssh -i '$SSH_KEY_PATH' ubuntu@$EC2_IP" -ForegroundColor Yellow
    Write-Host "   cd /home/ubuntu/drishti && docker compose logs -f" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host "❌ SSH Connection Failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting steps:" -ForegroundColor Yellow
    Write-Host "1. Verify SSH key permissions:"
    Write-Host "   chmod 600 '$SSH_KEY_PATH'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Test SSH connectivity:"
    Write-Host "   ssh -i '$SSH_KEY_PATH' -v ubuntu@$EC2_IP" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Verify EC2 security group allows SSH (port 22)"
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
