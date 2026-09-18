# DRISHTI Backup and Disaster Recovery Strategy

## Executive Summary

This document outlines the backup and disaster recovery (DR) strategy for the DRISHTI operations intelligence platform. The strategy ensures:

- **RTO (Recovery Time Objective)**: < 1 hour
- **RPO (Recovery Point Objective)**: < 15 minutes
- **Availability**: 99.9% SLA (4 nines)
- **Data Durability**: 99.999999999% (11 nines)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              DRISHTI Production                     │
│     (Multi-AZ ECS, RDS, Redis, S3)                 │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐
│RDS     │  │Redis   │  │   S3   │
│Backup  │  │AOF Log │  │Objects │
└───┬────┘  └───┬────┘  └───┬────┘
    │          │            │
    └──────────┼────────────┘
               │
        ┌──────▼──────┐
        │ AWS Backup  │
        │ Replication │
        │ (Cross-AZ)  │
        └──────┬──────┘
               │
        ┌──────▼──────────┐
        │  DR Site (AZ2)  │
        │  (Standby)      │
        └─────────────────┘
```

## Backup Strategy

### 1. Database Backups (RDS PostgreSQL)

#### Automated Backups
```hcl
# In terraform/database.tf

backup_retention_period = 30  # 30 days for production
backup_window           = "03:00-04:00"  # UTC

# Multi-AZ enabled for automatic failover
multi_az = true

# Encryption enabled
storage_encrypted = true
```

#### Manual Snapshots
```bash
# Create manual snapshot before major changes
aws rds create-db-snapshot \
  --db-instance-identifier drishti-db-production \
  --db-snapshot-identifier drishti-db-pre-migration-$(date +%Y%m%d-%H%M%S)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production

# Copy snapshot to different region for DR
aws rds copy-db-snapshot \
  --source-db-snapshot-identifier arn:aws:rds:us-east-1:111122223333:snapshot:mysql-instance1-snapshot-20130805 \
  --target-db-snapshot-identifier my-mysql-snapshot-copy \
  --region us-west-2
```

#### Backup Verification
```bash
#!/bin/bash
# Verify backups are running

# Check backup window
aws rds describe-db-instances \
  --db-instance-identifier drishti-db-production \
  --query 'DBInstances[0].[PreferredBackupWindow, BackupRetentionPeriod]'

# Check recent snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production \
  --query 'DBSnapshots[0:5].[DBSnapshotIdentifier, SnapshotCreateTime, Status]'
```

### 2. Redis Backups (ElastiCache)

#### Automated Snapshots
```hcl
# In terraform/database.tf

snapshot_retention_limit = 30  # 30 days for production
snapshot_window          = "03:00-05:00"  # UTC
automatic_failover_enabled = true
```

#### AOF (Append-Only File) Backup
```bash
# Enable AOF logging in Redis
aws elasticache modify-cache-cluster \
  --cache-cluster-id drishti-redis-production \
  --aof-enabled true
```

#### Export Snapshots
```bash
# Export Redis snapshot to S3
aws elasticache export-server-log \
  --cache-cluster-id drishti-redis-production \
  --log-delivery-configuration enabled=true,destination-type=s3,destination=my-redis-backup-bucket
```

### 3. Application Data Backups (S3)

#### Versioning
```hcl
# In terraform/main.tf

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  versioning_configuration {
    status = "Enabled"
  }
}
```

#### Cross-Region Replication
```bash
# Enable replication to DR region
aws s3api put-bucket-replication \
  --bucket drishti-data-us-east-1 \
  --replication-configuration '{
    "Role": "arn:aws:iam::123456789012:role/s3-replication",
    "Rules": [{
      "Status": "Enabled",
      "Priority": 1,
      "Destination": {
        "Bucket": "arn:aws:s3:::drishti-data-us-west-2",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": {"Minutes": 15}
        }
      }
    }]
  }'
```

### 4. Configuration and Code Backups

#### Infrastructure Code
```bash
# GitHub repository serves as primary backup
git push origin main
git push origin --tags

# Automated daily exports to S3
aws s3 sync ./terraform s3://drishti-backup/terraform --delete
aws s3 sync ./backend s3://drishti-backup/backend --delete
```

#### Secrets and Configuration
```bash
# Backup Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id drishti/database-url \
  > drishti-db-secret-backup.json

# Backup Parameter Store
aws ssm describe-parameters \
  --parameter-filters "Key=Name,Values=/drishti/*" \
  > drishti-parameters-backup.json

# Store encrypted in S3
aws s3api put-object \
  --bucket drishti-backup \
  --key secrets/drishti-db-secret-$(date +%Y%m%d).json.gpg \
  --body drishti-db-secret-backup.json \
  --sse AES256
```

## Backup Schedule

| Resource | Frequency | Retention | Window |
|---|---|---|---|
| RDS PostgreSQL | Automatic daily + Manual weekly | 30 days | 03:00-04:00 UTC |
| Redis Cache | Automatic daily + Manual weekly | 30 days | 03:00-05:00 UTC |
| S3 Objects | Continuous versioning | 90 days | N/A |
| ECS Task Logs | Daily | 7 days | N/A |
| Secrets Manager | Manual + Automated | 1 year | Off-peak |
| Code Repository | On-push | Forever | N/A |

## Recovery Procedures

### Scenario 1: Single Database Restore

**RTO**: 15 minutes | **RPO**: 5 minutes

```bash
# 1. List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production \
  --query 'DBSnapshots[?SnapshotType==`manual`]' \
  --output table

# 2. Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drishti-db-restored \
  --db-snapshot-identifier drishti-db-production-20231215-000000 \
  --db-subnet-group-name drishti-db-subnet-group \
  --vpc-security-group-ids sg-12345678

# 3. Wait for restoration
aws rds wait db-instance-available \
  --db-instance-identifier drishti-db-restored

# 4. Update connection string in Secrets Manager
aws secretsmanager update-secret \
  --secret-id drishti/database-url \
  --secret-string "postgresql://user:pass@drishti-db-restored.xxx.us-east-1.rds.amazonaws.com:5432/drishti_db"

# 5. Update ECS task definition
aws ecs update-service \
  --cluster drishti-cluster-production \
  --service drishti-service \
  --force-new-deployment
```

### Scenario 2: Redis Cache Restore

**RTO**: 10 minutes | **RPO**: 1 minute

```bash
# 1. Check snapshot status
aws elasticache describe-snapshots \
  --cache-cluster-id drishti-redis-production

# 2. Restore from snapshot
aws elasticache restore-cache-cluster \
  --cache-cluster-id drishti-redis-restored \
  --snapshot-name drishti-redis-production-2023-12-15-00-00

# 3. Wait for restoration
aws elasticache wait cache-cluster-available \
  --cache-cluster-id drishti-redis-restored

# 4. Update connection string
aws secretsmanager update-secret \
  --secret-id drishti/redis-url \
  --secret-string "redis://drishti-redis-restored.xxx.cache.amazonaws.com:6379?ssl=true"

# 5. Restart ECS tasks
aws ecs update-service \
  --cluster drishti-cluster-production \
  --service drishti-service \
  --force-new-deployment
```

### Scenario 3: Full Regional Failover

**RTO**: 30 minutes | **RPO**: 15 minutes

```bash
#!/bin/bash
# Full regional failover from us-east-1 to us-west-2

echo "=== DRISHTI Failover Script ==="
DR_REGION="us-west-2"

# 1. Copy RDS snapshot to DR region
echo "1. Copying RDS snapshot to $DR_REGION..."
aws rds copy-db-snapshot \
  --source-db-snapshot-identifier arn:aws:rds:us-east-1:123456789012:snapshot:drishti-latest-backup \
  --target-db-snapshot-identifier drishti-dr-restored \
  --region $DR_REGION

# 2. Wait for copy to complete
aws rds wait db-snapshot-completed \
  --db-snapshot-identifier drishti-dr-restored \
  --region $DR_REGION

# 3. Restore RDS in DR region
echo "2. Restoring RDS in $DR_REGION..."
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drishti-db-dr \
  --db-snapshot-identifier drishti-dr-restored \
  --region $DR_REGION

# 4. Restore Redis in DR region
echo "3. Restoring Redis cache in $DR_REGION..."
aws elasticache restore-cache-cluster \
  --cache-cluster-id drishti-redis-dr \
  --snapshot-name drishti-redis-latest-backup \
  --region $DR_REGION

# 5. Update Route 53 DNS to point to DR region
echo "4. Updating DNS to $DR_REGION..."
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.drishti.com",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [{"Value": "drishti-alb-dr.us-west-2.elb.amazonaws.com"}]
      }
    }]
  }'

# 6. Deploy application in DR region
echo "5. Deploying application in $DR_REGION..."
aws ecs create-service \
  --cluster drishti-cluster-dr \
  --service-name drishti-service-dr \
  --task-definition drishti-task \
  --desired-count 3 \
  --region $DR_REGION

echo "=== Failover Complete ==="
echo "API is now serving from $DR_REGION"
echo "Start investigation of primary region"
```

### Scenario 4: Data Corruption Recovery

**RTO**: 2 hours | **RPO**: 1 hour

```bash
# 1. Identify corruption time
# Check application logs and database activity logs

# 2. Find last clean backup before corruption
TIME_OF_CORRUPTION="2023-12-15 14:30:00"
aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production \
  --query "DBSnapshots[?SnapshotCreateTime<='$TIME_OF_CORRUPTION']" \
  --output table

# 3. Restore to point-in-time before corruption
RESTORE_TIME="2023-12-15 14:00:00"
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier drishti-db-production \
  --target-db-instance-identifier drishti-db-recovered \
  --restore-time "$RESTORE_TIME"

# 4. Verify data integrity
aws rds start-db-cluster-backup-restoration \
  --db-cluster-identifier drishti-db-recovered \
  --backup-id drishti-backup-clean

# 5. Run data consistency checks
psql -h drishti-db-recovered.xxx.us-east-1.rds.amazonaws.com -U postgres -d drishti_db << EOF
SELECT COUNT(*) FROM cascades;
SELECT COUNT(*) FROM alerts;
SELECT MAX(created_at) FROM alerts;
PRAGMA integrity_check;
EOF

# 6. If clean, promote to primary
aws rds modify-db-instance \
  --db-instance-identifier drishti-db-recovered \
  --apply-immediately

# 7. Update connection strings and redeploy
```

## Testing Recovery

### Monthly Backup Test

```bash
#!/bin/bash
# Monthly backup restoration test

echo "=== Monthly Backup Verification ==="

# 1. Test RDS restore
echo "Testing RDS restore..."
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drishti-test-restore \
  --db-snapshot-identifier drishti-db-production-$(date -d "last sunday" +%Y%m%d) \
  --publicly-accessible false

aws rds wait db-instance-available --db-instance-identifier drishti-test-restore

# 2. Verify database integrity
echo "Verifying RDS integrity..."
psql -h drishti-test-restore.xxx.us-east-1.rds.amazonaws.com -U postgres -d drishti_db << EOF
SELECT COUNT(*) as cascade_count FROM cascades;
SELECT COUNT(*) as alert_count FROM alerts;
SELECT COUNT(*) as user_count FROM users;
EOF

# 3. Clean up
echo "Cleaning up test resources..."
aws rds delete-db-instance \
  --db-instance-identifier drishti-test-restore \
  --skip-final-snapshot

echo "=== Backup Test Complete ==="
```

### Quarterly DR Drill

```bash
#!/bin/bash
# Quarterly full DR drill

echo "=== Quarterly DR Drill ==="
echo "This simulates a regional failure"

# 1. Create test environment in DR region
echo "1. Setting up test infrastructure in DR region..."
# Deploy test infrastructure mirroring production

# 2. Import latest backup
echo "2. Restoring from latest backup..."
# Execute full backup restore procedure

# 3. Run smoke tests
echo "3. Running smoke tests..."
pytest tests/smoke_tests.py --host=dr-test-endpoint

# 4. Measure RTO
RTO_MINUTES=$(calculate_recovery_time)
echo "Recovery Time Objective (RTO): ${RTO_MINUTES} minutes"

# 5. Verify RPO
RPO_MINUTES=$(calculate_data_loss)
echo "Recovery Point Objective (RPO): ${RPO_MINUTES} minutes"

# 6. Document results
echo "Drill results: $(date)" >> dr_drill_log.txt
echo "RTO: ${RTO_MINUTES} minutes" >> dr_drill_log.txt
echo "RPO: ${RPO_MINUTES} minutes" >> dr_drill_log.txt

# 7. Clean up
echo "4. Cleaning up test resources..."
terraform destroy -auto-approve

if [ $RTO_MINUTES -le 30 ] && [ $RPO_MINUTES -le 15 ]; then
  echo "✅ DR DRILL PASSED"
else
  echo "❌ DR DRILL FAILED - Review procedures and optimize"
fi

echo "=== DR Drill Complete ==="
```

## Monitoring and Alerting

### CloudWatch Alarms for Backups

```bash
# RDS Backup Status
aws cloudwatch put-metric-alarm \
  --alarm-name drishti-rds-backup-failed \
  --alarm-description "Alert if RDS backup fails" \
  --metric-name BackupStorageUsed \
  --namespace AWS/RDS \
  --statistic Average \
  --period 3600 \
  --threshold 0 \
  --comparison-operator LessThanOrEqualToThreshold

# ElastiCache Snapshot Status
aws cloudwatch put-metric-alarm \
  --alarm-name drishti-redis-snapshot-failed \
  --alarm-description "Alert if Redis snapshot fails" \
  --metric-name SnapshotStorageUsed \
  --namespace AWS/ElastiCache \
  --statistic Average \
  --period 3600 \
  --threshold 0 \
  --comparison-operator LessThanOrEqualToThreshold
```

### Backup Verification Automation

```bash
#!/bin/bash
# Daily backup verification script

SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Check RDS backup
RDS_BACKUP_AGE=$(aws rds describe-db-snapshots \
  --db-instance-identifier drishti-db-production \
  --query 'DBSnapshots[0].SnapshotCreateTime' \
  --output text)

RDS_BACKUP_HOURS=$(( ($(date +%s) - $(date -d "$RDS_BACKUP_AGE" +%s)) / 3600 ))

if [ $RDS_BACKUP_HOURS -gt 24 ]; then
  curl -X POST $SLACK_WEBHOOK \
    -H 'Content-Type: application/json' \
    -d '{"text":"⚠️ WARNING: RDS backup is '$RDS_BACKUP_HOURS' hours old!"}'
fi

# Check Redis backup
REDIS_BACKUP_AGE=$(aws elasticache describe-snapshots \
  --cache-cluster-id drishti-redis-production \
  --query 'Snapshots[0].SnapshotCreateTime' \
  --output text)

REDIS_BACKUP_HOURS=$(( ($(date +%s) - $(date -d "$REDIS_BACKUP_AGE" +%s)) / 3600 ))

if [ $REDIS_BACKUP_HOURS -gt 24 ]; then
  curl -X POST $SLACK_WEBHOOK \
    -H 'Content-Type: application/json' \
    -d '{"text":"⚠️ WARNING: Redis backup is '$REDIS_BACKUP_HOURS' hours old!"}'
fi
```

## SLA and Compliance

### Service Level Targets

```
Availability:        99.9% (4 nines, 43 minutes/month downtime)
RTO (Recovery Time): < 1 hour
RPO (Data Loss):     < 15 minutes
Backup Retention:    30 days (configurable)
Backup Verification: Monthly
DR Drill Frequency:  Quarterly
```

### Regulatory Compliance

- **GDPR**: Data backups encrypted, retention policies enforced
- **HIPAA**: Backups include audit logs, immutable backups (S3 Object Lock)
- **SOC 2**: Documented recovery procedures, automated testing
- **ISO 27001**: Access control, encryption in transit/rest

## Costs

### Backup Storage Costs (Monthly Estimate)

```
RDS Backup Storage:      ~$500  (30 days × 100GB database)
Redis Snapshots:         ~$50   (4-5 snapshots)
S3 Versioning:          ~$200   (100GB with versions)
Cross-region Replication:~$100  (Data transfer)
Snapshot Copy Costs:     ~$150  (To DR region)
─────────────────────────────
Total Monthly:          ~$1,000
```

### Cost Optimization

- Use S3 Intelligent-Tiering for old backups
- Delete unnecessary snapshots weekly
- Use lifecycle policies to transition old backups to Glacier
- Monitor backup storage usage

```bash
# Lifecycle policy for old backups
aws s3api put-bucket-lifecycle-configuration \
  --bucket drishti-backup \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "Archive-old-backups",
      "Status": "Enabled",
      "Transitions": [{
        "Days": 30,
        "StorageClass": "GLACIER"
      }],
      "Expiration": {"Days": 365}
    }]
  }'
```

## Runbook

### When Things Go Wrong

1. **Identify Problem**: Check CloudWatch, logs, application metrics
2. **Assess Impact**: Determine scope (single resource vs. regional)
3. **Select Strategy**: Choose appropriate recovery scenario
4. **Execute Recovery**: Run recovery procedure from this guide
5. **Verify**: Test all critical functions post-recovery
6. **Communicate**: Notify stakeholders of incident and recovery
7. **Investigate**: Root cause analysis, post-incident review
8. **Prevent**: Update procedures and improve preventive controls

## Key Contacts

| Role | Name | Phone | Email |
|---|---|---|---|
| On-Call Engineer | TBD | TBD | TBD |
| Platform Lead | TBD | TBD | TBD |
| Security Lead | TBD | TBD | TBD |
| AWS TAM | TBD | TBD | TBD |

## References

- [AWS RDS Backup](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_BackupRestore.html)
- [AWS ElastiCache Snapshots](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/using-redis-backup-restore.html)
- [Database Disaster Recovery](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/)
- [AWS Backup Center](https://docs.aws.amazon.com/aws-backup/latest/devguide/)

---

**Last Updated**: 2024-01-01
**Next Review**: 2024-04-01
**Approval**: Engineering Leadership
