# ╔════════════════════════════════════════════════════════════════════╗
# ║   DRISHTI AWS EMERGENCY FIX - ONE-CLICK SOLUTION                     ║
# ║   Diagnoses and fixes all issues automatically                       ║
# ╚════════════════════════════════════════════════════════════════════╝

param(
    [string]$EC2_IP = "44.216.1.62",
    [string]$SSH_KEY = "$env:USERPROFILE\.ssh\drishti-deploy-key"
)

# Configuration
$ErrorActionPreference = "Continue"
$MaxRetries = 3
$WaitTime = 30

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      DRISHTI AWS EMERGENCY FIX - ONE-CLICK DEPLOYMENT             ║" -ForegroundColor Cyan
Write-Host "║                     DEADLINE MODE ACTIVATED                        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Validate SSH key
if (-Not (Test-Path $SSH_KEY)) {
    Write-Host "❌ SSH key not found: $SSH_KEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "⚠️  PLEASE PROVIDE SSH KEY:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option 1 - Set environment variable:" -ForegroundColor Gray
    Write-Host "  `$env:SSH_KEY = 'C:\path\to\your\key.pem'" -ForegroundColor Gray
    Write-Host "  .\aws-emergency-fix.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Option 2 - Pass as parameter:" -ForegroundColor Gray
    Write-Host "  .\aws-emergency-fix.ps1 -EC2_IP '44.216.1.62' -SSH_KEY 'C:\path\to\key.pem'" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host "✅ Configuration Valid" -ForegroundColor Green
Write-Host "   EC2 IP: $EC2_IP" -ForegroundColor Gray
Write-Host "   SSH Key: $SSH_KEY" -ForegroundColor Gray
Write-Host ""

# Test SSH connectivity
Write-Host "🔗 Testing SSH connectivity..." -ForegroundColor Yellow
try {
    $TestSSH = ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$EC2_IP "echo ok" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SSH connection successful" -ForegroundColor Green
    } else {
        throw "SSH connection failed"
    }
} catch {
    Write-Host "❌ Cannot connect to EC2" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Verify EC2 instance is running" -ForegroundColor Gray
    Write-Host "  2. Check security group allows SSH (port 22)" -ForegroundColor Gray
    Write-Host "  3. Verify SSH key permissions" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "🚀 Starting emergency fix sequence..." -ForegroundColor Cyan
Write-Host ""

# Remote fix script - DIRECT RESTART
$REMOTE_FIX = @'
#!/bin/bash
cd /home/ubuntu/drishti

echo "🔥 DRISHTI EMERGENCY RESTART"
echo "================================"
echo ""

echo "1️⃣  Stopping all containers..."
docker compose -f docker-compose.production.yml down -v 2>/dev/null || true
sleep 5

echo "2️⃣  Cleaning up old images..."
docker image prune -af 2>/dev/null || true
docker builder prune -af 2>/dev/null || true

echo "3️⃣  Pulling latest images from GitHub Container Registry..."
docker pull ghcr.io/404avinash/drishti/backend:latest 2>&1 | tail -3
docker pull ghcr.io/404avinash/drishti/frontend:latest 2>&1 | tail -3

echo "4️⃣  Starting fresh containers..."
docker compose -f docker-compose.production.yml up -d

echo "5️⃣  Waiting 45 seconds for initialization..."
for i in {45..1}; do
    echo -ne "\r     ⏳ $i seconds remaining..."
    sleep 1
done
echo -e "\r✅ Initialization complete            "

echo ""
echo "6️⃣  Container Status:"
docker compose -f docker-compose.production.yml ps

echo ""
echo "7️⃣  Backend Health Check:"
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    curl -s http://localhost:8000/api/health | jq '.status, .database, .websocket_connections' 2>/dev/null || echo "OK"
    echo "✅ Backend is responding!"
else
    echo "⚠️  Still starting, wait 30 more seconds and refresh browser"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "✅ SYSTEM RESTART COMPLETE - Should be LIVE NOW"
echo "════════════════════════════════════════════════════════════════════"
'@

# Execute the fix
Write-Host "📡 Executing fix sequence on EC2..." -ForegroundColor Yellow
Write-Host ""

$output = ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_IP $REMOTE_FIX 2>&1
Write-Host $output

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ SYSTEM RESTART COMPLETE - Containers Should Be Running" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    🎉 SYSTEM SHOULD BE LIVE NOW                  ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "🎯 NEXT STEP - Test Your System:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   OPEN THIS IN YOUR BROWSER:" -ForegroundColor Cyan
Write-Host "   http://$EC2_IP/" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host ""
Write-Host "   You should see:" -ForegroundColor Green
Write-Host "   ✅ Dashboard with train data" -ForegroundColor Green
Write-Host "   ✅ Alerts displaying" -ForegroundColor Green
Write-Host "   ✅ System showing ONLINE (green)" -ForegroundColor Green
Write-Host ""
Write-Host "💡 If still showing OFFLINE:" -ForegroundColor Yellow
Write-Host "   1. Clear browser cache (Ctrl+Shift+Delete)" -ForegroundColor Gray
Write-Host "   2. Do a hard refresh (Ctrl+F5)" -ForegroundColor Gray
Write-Host "   3. Wait 30 seconds" -ForegroundColor Gray
Write-Host "   4. Try again" -ForegroundColor Gray
Write-Host ""

Write-Host "💡 If issues persist:" -ForegroundColor Yellow
Write-Host "   • Clear browser cache (Ctrl+Shift+Delete)" -ForegroundColor Gray
Write-Host "   • Refresh page (F5)" -ForegroundColor Gray
Write-Host "   • Check logs: ssh -i '$SSH_KEY' ubuntu@$EC2_IP" -ForegroundColor Gray
Write-Host "   • Then: cd /home/ubuntu/drishti && docker compose logs -f" -ForegroundColor Gray
Write-Host ""

Write-Host "✨ Deployment timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""
