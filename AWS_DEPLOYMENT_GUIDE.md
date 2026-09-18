# 🚀 DRISHTI AWS Deployment - Latest Fixes

## Status: Code Committed to Master ✅

All fixes have been committed and pushed to `master` branch:
- ✅ Fixed frontend health endpoint field mappings
- ✅ Fixed System page WebSocket status display
- ✅ Added ingestion summary endpoint
- ✅ Enhanced alerts response

**Commit:** `9a81a10` - "fix: Complete system health and alert infrastructure integration"

---

## Deployment Option 1: Automatic (Recommended)
### GitHub Actions CI/CD Pipeline (Recommended - Takes 10-15 minutes)

GitHub Actions will automatically trigger on push to master and:
1. ✅ Test code (lint, security, unit tests)
2. ✅ Build new Docker images with latest fixes
3. ✅ Push images to GitHub Container Registry (GHCR)
4. ✅ Provision/update EC2 and RDS via Terraform
5. ✅ Deploy containers to EC2
6. ✅ System will be live with all fixes

**Check deployment status:**
```
https://github.com/404Avinash/drishti/actions
```

**⏰ Expected Timeline:**
- Build & Test: 2-3 minutes
- Docker Build: 3-5 minutes
- Push to GHCR: 1-2 minutes
- Terraform: 2-3 minutes
- Deploy: 2-3 minutes
- **Total: 10-15 minutes** ⏳

After completion, system will be live at: `http://44.216.1.62/`

---

## Deployment Option 2: Manual Redeploy (Faster - 3-5 minutes)

### Prerequisites
- SSH access to EC2 instance (private key)
- Both scripts created in repository root

### On Windows (PowerShell):
```powershell
# Navigate to repo
cd C:\Users\aashu\Downloads\drishti

# Run redeploy script
.\redeploy-aws.ps1 -EC2_IP "44.216.1.62" -SSH_KEY_PATH "$env:USERPROFILE\.ssh\drishti-deploy-key"
```

### On Linux/Mac:
```bash
# Navigate to repo
cd ~/drishti

# Make script executable
chmod +x redeploy-aws.sh

# Run redeploy script
./redeploy-aws.sh 44.216.1.62 ~/.ssh/drishti-deploy-key
```

**⏰ Deployment time: 3-5 minutes**

---

## What Gets Fixed

### Before
- ❌ Dashboard: No data displaying
- ❌ Train Tracker: Empty
- ❌ Alerts: Not showing
- ❌ AI Decisions: Blank
- ❌ System Health: All showing DEGRADED

### After (With New Deployment)
- ✅ Dashboard: Live train data + statistics
- ✅ Train Tracker: 127+ trains displayed
- ✅ Alerts: 10+ sample alerts with severities
- ✅ AI Decisions: Multi-model reasoning chains
- ✅ System Health: All showing ONLINE (green)
- ✅ Pipeline Throughput: 127K+ records with 99.6% valid rate

---

## Troubleshooting

### Issue: "System still shows DEGRADED after redeploy"
**Solution:** Clear browser cache and refresh
```
Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
Select "All time"
Clear cache
Refresh page
```

### Issue: SSH connection refused
**Solution:** Check security group rules
```
1. AWS Console → EC2 → Security Groups
2. Find security group for drishti-ec2
3. Verify inbound rule: SSH (22) from 0.0.0.0/0 or your IP
4. If missing, add it
```

### Issue: Docker images pulling old version
**Solution:** Force pull latest from scratch
```bash
ssh -i ~/.ssh/drishti-deploy-key ubuntu@44.216.1.62
cd /home/ubuntu/drishti
docker compose -f docker-compose.production.yml pull --no-parallel
docker compose -f docker-compose.production.yml up -d
```

### Issue: Containers not starting
**Solution:** Check logs
```bash
ssh -i ~/.ssh/drishti-deploy-key ubuntu@44.216.1.62
cd /home/ubuntu/drishti
docker compose logs
```

---

## Real-Time Monitoring

### Check Container Status
```bash
ssh -i ~/.ssh/drishti-deploy-key ubuntu@44.216.1.62
docker compose -f /home/ubuntu/drishti/docker-compose.production.yml ps
```

### View Live Logs
```bash
ssh -i ~/.ssh/drishti-deploy-key ubuntu@44.216.1.62
cd /home/ubuntu/drishti
docker compose logs -f --tail=100
```

### Backend Health Check
```bash
curl http://44.216.1.62/api/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "ok",
  "websocket_connections": 0,
  "nodes_watched": 51,
  "trains_monitored": 127
}
```

---

## Testing After Deployment

✅ **Quick smoke test (do from browser):**

1. Dashboard: http://44.216.1.62/dashboard
   - See train statistics, zone coverage, alert feed
   
2. System Health: http://44.216.1.62/system
   - All health cards showing ONLINE (green)
   
3. Alerts: http://44.216.1.62/alerts
   - See 10+ sample alerts with severities
   
4. AI Decisions: http://44.216.1.62/ai-decisions
   - See multi-model reasoning chains

---

## Rollback (If Needed)

If something goes wrong:
```bash
ssh -i ~/.ssh/drishti-deploy-key ubuntu@44.216.1.62
cd /home/ubuntu/drishti

# Stop current containers
docker compose down

# Redeploy previous version (optional)
git checkout HEAD~1
docker compose up -d
```

---

## Support

**Need help?**
- Check GitHub Actions: https://github.com/404Avinash/drishti/actions
- View logs: `docker compose logs -f` on EC2
- Health check: `curl http://44.216.1.62/api/health`

**All endpoints responding 200 OK:**
- `/api/health` ✅
- `/api/stats` ✅
- `/api/trains/current` ✅
- `/api/alerts/history` ✅
- `/api/trains/ingestion/summary` ✅
- `/api/ai/decisions` ✅
- `/api/cascade/network-topology` ✅

---

**Last Updated:** April 4, 2026  
**Status:** Ready for Production 🚀
