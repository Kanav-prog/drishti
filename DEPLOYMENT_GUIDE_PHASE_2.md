ok # DRISHTI Deployment Guide - DARPA Level

## Table of Contents

1. [Overview](#overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Application Deployment](#application-deployment)
5. [Verification and Testing](#verification-and-testing)
6. [Production Deployment](#production-deployment)
7. [Monitoring and Operations](#monitoring-and-operations)
8. [Troubleshooting](#troubleshooting)
9. [Rollback Procedures](#rollback-procedures)

---

## Overview

DRISHTI is an enterprise-grade Operations Intelligence Platform designed for real-time cascade risk monitoring in railway networks. The deployment follows a **4-layer architecture**:

- **Layer 1 (Map)**: Network graph with centrality analysis
- **Layer 2 (Pulse)**: Real-time NTES operations monitoring
- **Layer 3 (Intelligence)**: Signature-based cascade pattern detection
- **Layer 4 (Dashboard)**: Real-time visualization and alerting

### Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│           Internet / Client Apps                    │
└────────────────────┬────────────────────────────────┘
                     │
          ┌──────────▼────────────┐
          │  AWS CloudFront (CDN) │
          └──────────┬────────────┘
                     │
          ┌──────────▼────────────┐
          │ Application Load      │
          │ Balancer (ALB) :443   │
          └──────────┬────────────┘
                     │
   ┌─────────────────┼─────────────────┐
   │                 │                 │
┌──▼──┐          ┌───▼───┐         ┌──▼──┐
│ AZ1 │          │ AZ2   │         │ AZ3 │
│ECS  │          │ ECS   │         │ ECS │
└──┬──┘          └───┬───┘         └──┬──┘
   │                 │                 │
   └─────────────────┼─────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
    ┌───▼────┐  ┌───▼────┐  ┌───▼────┐
    │ RDS    │  │ Redis  │  │   S3   │
    │ Multi- │  │ Multi- │  │ Object │
    │ AZ     │  │ AZ     │  │ Store  │
    └────────┘  └────────┘  └────────┘

```

---

## Pre-Deployment Checklist

### AWS Account Setup

- [ ] AWS Account created with billing enabled
- [ ] IAM user with sufficient permissions (`AdministratorAccess` or custom policy)
- [ ] AWS CLI configured: `aws configure`
- [ ] AWS credentials stored in `~/.aws/credentials`
- [ ] Region set to `us-east-1` (primary) with DR region `us-west-2`

### Required Tools

```bash
# Verify installations
terraform -version        # v1.0+
aws --version            # v2.0+
docker --version         # v20.0+
kubectl version          # v1.24+ (optional)
locust --version         # Optional, for load testing
```

### Prerequisites

- [ ] Git repository cloned and branches verified
- [ ] GitHub personal access token created (for GHCR)
- [ ] Docker images built and pushed to GHCR
- [ ] Terraform files reviewed and customized
- [ ] Secrets and credentials prepared

### AWS Resource Quotas

```bash
# Check and increase if needed
aws service-quotas get-service-quota \
  --service-code ecs \
  --quota-code L-971BA2D6  # On-Demand vCPU count

aws service-quotas get-service-quota \
  --service-code rds \
  --quota-code L-7B6409FD  # DB instances
```

---

## Infrastructure Setup

### Step 1: Prepare AWS Backend

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket drishti-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket drishti-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket drishti-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
    }]
  }'

# Enable public access block
aws s3api put-public-access-block \
  --bucket drishti-terraform-state \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name drishti-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Step 2: Initialize Terraform

```bash
cd terraform

# Initialize with S3 backend
terraform init \
  -backend-config="bucket=drishti-terraform-state" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true" \
  -backend-config="dynamodb_table=drishti-tfstate-lock"

# Verify initialization
terraform validate
terraform fmt
```

### Step 3: Deploy Staging Environment

```bash
# Plan staging deployment
terraform plan \
  -var-file="staging.tfvars" \
  -var="db_username=postgres" \
  -var="db_password=$(pwgen -s 32 1)" \
  -var="container_image=ghcr.io/drishti-ai/drishti-backend:develop" \
  -out=tfplan-staging

# Review plan carefully
# 3 subnets, 4 security groups, 1 ALB, 1 ECS cluster, 1 RDS, 1 Redis

# Apply staging deployment
terraform apply tfplan-staging

# Retrieve outputs
terraform output -json > staging-outputs.json
```

### Step 4: Deploy Production Environment

```bash
# Create separate Terraform workspace for production
terraform workspace new production
terraform workspace select production

# Plan production deployment
terraform plan \
  -var-file="prod.tfvars" \
  -var="db_username=postgres" \
  -var="db_password=$(pwgen -s 32 1)" \
  -var="container_image=ghcr.io/drishti-ai/drishti-backend:latest" \
  -out=tfplan-prod

# Review plan for multi-AZ resources
# Should include: 6 subnets (3 AZs × 2), Multi-AZ RDS, Multi-AZ Redis

# Apply production deployment (careful!)
terraform apply tfplan-prod

# Verify all resources created
terraform output -json | jq '.infrastructure_summary.value'
```

---

## Application Deployment

### Step 1: Build Docker Images

```bash
# Login to GitHub Container Registry
echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin

# Build backend image
docker build -t ghcr.io/drishti-ai/drishti-backend:latest \
  -t ghcr.io/drishti-ai/drishti-backend:$(git describe --tags) \
  -f backend/Dockerfile \
  .

# Build frontend image (optional)
docker build -t ghcr.io/drishti-ai/drishti-frontend:latest \
  -t ghcr.io/drishti-ai/drishti-frontend:$(git describe --tags) \
  -f frontend/Dockerfile \
  .

# Push to registry
docker push ghcr.io/drishti-ai/drishti-backend:latest
docker push ghcr.io/drishti-ai/drishti-backend:$(git describe --tags)
```

### Step 2: Configure Secrets

```bash
# Database credentials
aws secretsmanager create-secret \
  --name drishti/database-url \
  --description "DRISHTI database connection string" \
  --secret-string "postgresql://postgres:PASSWORD@drishti-db-production.xxx.us-east-1.rds.amazonaws.com:5432/drishti_db?sslmode=require"

# Redis connection
aws secretsmanager create-secret \
  --name drishti/redis-url \
  --description "DRISHTI Redis connection string" \
  --secret-string "redis://:PASSWORD@drishti-redis-production.xxx.cache.amazonaws.com:6379?ssl=true"

# JWT secret for authentication
aws secretsmanager create-secret \
  --name drishti/jwt-secret \
  --description "JWT secret for token signing" \
  --secret-string "$(openssl rand -base64 32)"

# API keys for external services
aws secretsmanager create-secret \
  --name drishti/ntes-api-key \
  --description "NTES API credentials" \
  --secret-string '{"api_key":"xxx","api_url":"https://api.ntes.gov.in"}'
```

### Step 3: Deploy ECS Service

```bash
# Register task definition
aws ecs register-task-definition \
  --family drishti \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 256 \
  --memory 512 \
  --execution-role-arn arn:aws:iam::ACCOUNT:role/drishti-ecs-task-execution-role \
  --task-role-arn arn:aws:iam::ACCOUNT:role/drishti-ecs-task-role \
  --container-definitions '[
    {
      "name": "drishti",
      "image": "ghcr.io/drishti-ai/drishti-backend:latest",
      "containerPort": 8000,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/drishti",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "LOG_LEVEL", "value": "INFO"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:drishti/database-url"},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:drishti/redis-url"}
      ]
    }
  ]'

# Create service in staging first
aws ecs create-service \
  --cluster drishti-cluster-staging \
  --service-name drishti-service \
  --task-definition drishti:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:targetgroup/drishti-tg-staging/xxx,containerName=drishti,containerPort=8000 \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100,deploymentCircuitBreaker={enable=true,rollback=true}"

# Wait for service to stabilize
aws ecs wait services-stable \
  --cluster drishti-cluster-staging \
  --services drishti-service
```

### Step 4: Configure Service Auto-Scaling

```bash
# Register ECS service target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/drishti-cluster-production/drishti-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 3 \
  --max-capacity 20

# CPU-based scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name drishti-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/drishti-cluster-production/drishti-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
  "TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization},ScaleOutCooldown=60,ScaleInCooldown=300"
```

### Step 5: Setup ELK Stack

```bash
# Create .env file
echo "ELASTIC_PASSWORD=$(pwgen -s 32 1)" > .env

# Deploy ELK stack (if using Docker Compose)
docker-compose -f docker-compose.elk.yml up -d

# Or deploy to ECS for production
aws ecs create-service \
  --cluster drishti-elk-cluster \
  --service-name elasticsearch \
  --task-definition elasticsearch:1 \
  --desired-count 1

# Verify Kibana is accessible
curl http://localhost:5601/api/status
```

---

## Verification and Testing

### Step 1: Health Checks

```bash
# Get ALB DNS
ALB_DNS=$(terraform output -raw alb_dns_name)

# Health check endpoint
curl -k https://$ALB_DNS/health

# Should return: {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}
```

### Step 2: Integration Tests

```bash
# Run integration tests against staging
pytest tests/test_integration.py \
  --host=https://$ALB_DNS \
  -v

# Key tests:
# - Network graph creation
# - Cascade simulation
# - Alert generation
# - WebSocket connections
# - Database operations
```

### Step 3: Performance Baseline

```bash
# Run load test (light: 10 users)
locust -f tests/load_test.py \
  --host=https://$ALB_DNS \
  -u 10 -r 1 -t 300 \
  --headless \
  --csv=baseline

# Check response times
# P95 should be < 500ms, P99 < 1000ms
```

### Step 4: Security Validation

```bash
# OWASP Dependency Check
dependency-check --project "DRISHTI" --scan .

# Bandit security check
bandit -r backend/ -f json -o bandit-report.json

# SAST scanning
sonarqube-scanner \
  -Dsonar.projectKey=drishti-backend \
  -Dsonar.sources=backend
```

---

## Production Deployment

### Step 1: Pre-Production Checklist

```bash
# 1. Database backups verified
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-staging

# 2. Secrets configured
aws secretsmanager list-secrets | grep drishti

# 3. Monitoring configured
aws cloudwatch describe-alarms | grep drishti

# 4. Backups enabled
aws rds describe-db-instances \
  --query 'DBInstances[0].[BackupRetentionPeriod,MultiAZ]'

# 5. Load test passed
# Review load_test_results_stats.csv

# 6. Security scan passed
# Review security reports
```

### Step 2: Blue-Green Deployment

```bash
#!/bin/bash
# Blue-green deployment script

CLUSTER="drishti-cluster-production"
SERVICE="drishti-service"
REGION="us-east-1"

echo "=== Starting Blue-Green Deployment ==="

# 1. Get current service (Blue)
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION \
  --query 'services[0].taskDefinition' \
  --output text)

echo "Blue deployment: $CURRENT_TASK_DEF"

# 2. Register new task definition (Green)
NEW_TASK_DEF=$(aws ecs register-task-definition \
  --family drishti \
  --container-definitions '[
    {
      "name": "drishti",
      "image": "ghcr.io/drishti-ai/drishti-backend:latest",
      "containerPort": 8000
    }
  ]' \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)

echo "Green deployment: $NEW_TASK_DEF"

# 3. Update service to use Green
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --task-definition $NEW_TASK_DEF \
  --force-new-deployment \
  --region $REGION

# 4. Wait for deployment to complete
aws ecs wait services-stable \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION

# 5. Run smoke tests on Green
echo "Running smoke tests..."
python -m pytest tests/smoke_tests.py --host=https://api.drishti.com

if [ $? -eq 0 ]; then
  echo "✅ Smoke tests passed - Green is healthy"
  
  # 6. Scale down Blue (optional)
  # aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 0
  
  echo "✅ Deployment complete"
else
  echo "❌ Smoke tests failed - Rolling back"
  
  # Rollback to Blue
  aws ecs update-service \
    --cluster $CLUSTER \
    --service $SERVICE \
    --task-definition $CURRENT_TASK_DEF \
    --force-new-deployment \
    --region $REGION
  
  echo "❌ Rolled back to previous version"
fi
```

### Step 3: Smoke Tests for Production

```bash
# Quick verification that everything works
python << 'EOF'
import requests
import json
import time

BASE_URL = "https://api.drishti.com"
TIMEOUT = 5

tests = [
    ("Health Check", f"{BASE_URL}/health"),
    ("Network Stats", f"{BASE_URL}/api/v1/network/stats"),
    ("Cascades List", f"{BASE_URL}/api/v1/cascades?limit=1"),
]

print("Running smoke tests...")
all_passed = True

for test_name, url in tests:
    try:
        response = requests.get(url, timeout=TIMEOUT, verify=True)
        if response.status_code == 200:
            print(f"✅ {test_name}: {response.status_code}")
        else:
            print(f"❌ {test_name}: {response.status_code}")
            all_passed = False
    except Exception as e:
        print(f"❌ {test_name}: {str(e)}")
        all_passed = False

if all_passed:
    print("\n✅ All smoke tests passed!")
    exit(0)
else:
    print("\n❌ Some tests failed")
    exit(1)
EOF
```

### Step 4: Post-Deployment Verification

```bash
# 1. Check ECS service health
aws ecs describe-services \
  --cluster drishti-cluster-production \
  --services drishti-service \
  --query 'services[0].[runningCount,desiredCount,deployments]'

# 2. Check database connectivity
psql -h $(terraform output -raw rds_address) \
  -U postgres -d drishti_db \
  -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"

# 3. Check Redis connectivity
redis-cli -h $(terraform output -raw redis_endpoint) PING

# 4. Check ALB health
aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -raw target_group_arn) \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State]'

# 5. Check CloudWatch logs
aws logs tail /ecs/drishti --follow --since 5m

# 6. Verify metrics are flowing
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=drishti-service \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

---

## Monitoring and Operations

### Step 1: Setup CloudWatch Dashboards

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name DRISHTI-Production \
  --dashboard-body file://dashboard-config.json
```

### Step 2: Configure Alerts

```bash
# High error rate alert
aws cloudwatch put-metric-alarm \
  --alarm-name drishti-high-error-rate \
  --alarm-description "Alert when error rate > 5%" \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:drishti-alerts

# High response time alert
aws cloudwatch put-metric-alarm \
  --alarm-name drishti-high-response-time \
  --alarm-description "Alert when P95 response time > 2s" \
  --metric-name TargetResponseTime \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 300 \
  --threshold 2.0 \
  --comparison-operator GreaterThanThreshold
```

### Step 3: Enable Detailed Monitoring

```bash
# RDS Enhanced Monitoring
aws rds modify-db-instance \
  --db-instance-identifier drishti-db-production \
  --monitoring-interval 60 \
  --monitoring-role-arn arn:aws:iam::ACCOUNT:role/drishti-rds-monitoring \
  --enable-cloudwatch-logs-exports postgresql

# ECS Container Insights
aws ecs create-cluster \
  --cluster-name drishti-cluster-production \
  --settings name=containerInsights,value=enabled
```

### Step 4: Setup Performance Baselines

```bash
# Document baseline metrics
echo "BASELINE METRICS" > baseline-metrics.txt
echo "Timestamp: $(date)" >> baseline-metrics.txt
echo "P50 Response Time: $(aws cloudwatch get-metric-statistics --metric-name TargetResponseTime --namespace AWS/ApplicationELB --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --end-time $(date -u +%Y-%m-%dT%H:%M:%S) --period 3600 --statistics Average | jq '.Datapoints[0].Average')" >> baseline-metrics.txt
echo "Error Rate: $(aws cloudwatch get-metric-statistics --metric-name HTTPCode_Target_5XX_Count --namespace AWS/ApplicationELB --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --end-time $(date -u +%Y-%m-%dT%H:%M:%S) --period 3600 --statistics Sum | jq '.Datapoints[0].Sum')" >> baseline-metrics.txt
```

---

## Troubleshooting

### Issue: ECS Tasks Not Starting

```bash
# 1. Check task definition
aws ecs describe-task-definition \
  --task-definition drishti:1

# 2. Check service events
aws ecs describe-services \
  --cluster drishti-cluster-production \
  --services drishti-service \
  --query 'services[0].events'

# 3. Check cloudwatch logs
aws logs tail /ecs/drishti --follow

# 4. Common issues:
# - Missing secrets: Verify secretsmanager entries
# - Image not found: Check ECR credentials
# - Container port mismatch: Verify port in task def vs security group
```

### Issue: Database Connection Failures

```bash
# 1. Test RDS connectivity
nc -zv $(terraform output -raw rds_address) 5432

# 2. Check security groups
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw rds_security_group_id) \
  --query 'SecurityGroups[0].IpPermissions'

# 3. Check connection string in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id drishti/database-url

# 4. Test with psql
psql "postgresql://postgres:PASSWORD@ENDPOINT:5432/drishti_db?sslmode=require"
```

### Issue: High Memory Usage

```bash
# 1. Check current memory usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=drishti-service \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Maximum

# 2. Check task definitions
aws ecs describe-task-definition \
  --task-definition drishti:1 \
  --query 'taskDefinition.memory'

# 3. Scale up memory
aws ecs register-task-definition \
  --family drishti \
  --memory 1024 \
  # ... other parameters
```

### Issue: WebSocket Connection Failures

```bash
# 1. Test WebSocket connectivity
wscat -c wss://api.drishti.com/ws/alerts

# 2. Check ALB WebSocket support
# Sticky sessions enabled: Yes
# Deregistration delay: 300 seconds

# 3. Review ECS logs for WebSocket errors
aws logs filter-log-events \
  --log-group-name /ecs/drishti \
  --filter-pattern "WebSocket"
```

---

## Rollback Procedures

### Quick Rollback

```bash
# Rollback to previous task definition
PREVIOUS_TASK=$(aws ecs describe-services \
  --cluster drishti-cluster-production \
  --services drishti-service \
  --query 'services[0].deployments[1].taskDefinition' \
  --output text)

aws ecs update-service \
  --cluster drishti-cluster-production \
  --service drishti-service \
  --task-definition $PREVIOUS_TASK \
  --force-new-deployment

# Wait for rollback
aws ecs wait services-stable \
  --cluster drishti-cluster-production \
  --services drishti-service
```

### Full Rollback (Terraform)

```bash
# If infrastructure changes broke something
terraform plan -destroy -var-file="prod.tfvars"

# Review carefully!
terraform apply -destroy -var-file="prod.tfvars"

# Then redeploy with known-good configuration
terraform apply -var-file="prod.tfvars"
```

---

## Operations Runbook

### Daily Operations

```bash
#!/bin/bash
# Daily operations check

echo "=== Daily Health Check ==="
date

# 1. Service status
echo "1. ECS Service Status:"
aws ecs describe-services \
  --cluster drishti-cluster-production \
  --services drishti-service \
  --query 'services[0].[serviceName,runningCount,desiredCount,deployments[0].status]'

# 2. Database status
echo "2. RDS Database Status:"
aws rds describe-db-instances \
  --db-instance-identifier drishti-db-production \
  --query 'DBInstances[0].[DBInstanceStatus, MultiAZ, BackupRetentionPeriod]'

# 3. Error count in last hour
echo "3. Error Rate (Last Hour):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum

# 4. Backup status
echo "4. Latest Backup:"
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production \
  --max-records 1 \
  --query 'DBSnapshots[0].[DBSnapshotIdentifier, SnapshotCreateTime, Status]'

echo "=== Daily Health Check Complete ==="
```

### Weekly Maintenance

- [ ] Review CloudWatch logs for errors
- [ ] Check backup status and retention
- [ ] Verify auto-scaling policies
- [ ] Review security group rules
- [ ] Update documentation
- [ ] Test disaster recovery procedures

### Monthly Tasks

- [ ] Full backup verification test
- [ ] Load test to establish baselines
- [ ] Security audit (Bandit, Trivy, OWASP)
- [ ] Cost analysis
- [ ] Capacity planning review
- [ ] Performance optimization review

---

## Support and Escalation

### Emergency Contacts

| Role | Contact | Escalation |
|---|---|---|
| On-Call Engineer | [TBD] | Page on-call |
| Platform Lead | [TBD] | Email + Slack |
| AWS Support | [Enterprise Support] | TAM |

### Incident Response Process

1. **Detect**: CloudWatch alarms → Slack notification
2. **Assess**: Check logs, metrics, service status
3. **Mitigate**: Execute appropriate runbook procedure
4. **Resolve**: Fix root cause, verify stability
5. **Communicate**: Status updates to stakeholders
6. **Retrospective**: Post-mortem, process improvements

---

## References

- [AWS ECS Deployment Guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest)
- [DRISHTI Architecture](./DRISHTI_PLAN.md)
- [Load Testing Guide](./LOAD_TESTING_GUIDE.md)
- [Backup Strategy](./BACKUP_AND_DR_STRATEGY.md)
- [ELK Integration](./ELK_INTEGRATION.md)

---

**Last Updated**: 2024-01-01
**Version**: 1.0.0  
**Status**: Production Ready
