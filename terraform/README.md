# Terraform Infrastructure for DRISHTI

This directory contains the complete infrastructure-as-code (IaC) for deploying DRISHTI on AWS using Terraform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Internet (0.0.0.0/0)                  │
└────────────────────────┬────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │   ALB    │ (Application Load Balancer)
                    │ :80/443  │
                    └────┬────┘
          ┌─────────────┼─────────────┐
          │             │             │
     ┌────▼──┐   ┌─────▼────┐  ┌────▼──┐
     │  AZ1  │   │   AZ2    │  │  AZ3  │
     └────┬──┘   └─────┬────┘  └────┬──┘
          │             │            │
     ┌────▼──────────────▼────────────▼────┐
     │     ECS Cluster (Fargate)           │
     │  - 2-10 tasks (auto-scaling)        │
     │  - Blue-green deployment            │
     │  - Canary rollout (optional)        │
     └────────────────────────────────────┘
          │
     ┌────┴────┬────────────┬─────────────┐
     │          │            │             │
  ┌──▼─┐    ┌──▼─┐      ┌───▼──┐      ┌──▼──┐
  │RDS │    │ S3 │      │Redis │      │ELK  │
  │ DB │    │... │      │Cache │      │Log  │
  └────┘    └────┘      └──────┘      └─────┘
```

## Infrastructure Components

### 1. **Networking** (`networking.tf`)
- **VPC**: 10.0.0.0/16 CIDR block across 2 AZs
- **Public Subnets**: 10.0.1.0/24, 10.0.2.0/24 (NAT Gateways, ALB)
- **Private Subnets**: 10.0.10.0/24, 10.0.11.0/24 (ECS tasks, RDS, Redis)
- **Security Groups**: ALB, ECS, RDS, Redis with restricted ingress rules
- **NAT Gateways**: High availability across AZs

### 2. **Compute** (`compute.tf`)
- **ECS Cluster**: Fargate-based container orchestration
- **Task Definition**: CPU 256, Memory 512 (configurable)
- **Service**: 2-3 desired tasks with auto-scaling (min 2, max 10)
- **Auto Scaling**: CPU (70%) and Memory (80%) based scaling policies
- **Deployment Circuit Breaker**: Automatic rollback on deployment failure
- **IAM Roles**: Task execution and application-level permissions

### 3. **Database** (`database.tf`)
- **RDS PostgreSQL**: 
  - Version 15.3 (configurable)
  - Multi-AZ for production
  - Automated backups (7-30 days retention)
  - Performance Insights enabled (production)
  - Encryption at rest (KMS)
  - Enhanced monitoring with CloudWatch logs
  
- **ElastiCache Redis**:
  - Version 7.0
  - Multi-AZ with automatic failover (production)
  - At-rest and in-transit encryption
  - Backup snapshots (production only)
  - Slow log and engine log to CloudWatch
  
- **Secrets Manager**: Database and Redis connection strings stored securely

### 4. **Load Balancer** (`loadbalancer.tf`)
- **Application Load Balancer**: HTTP → HTTPS redirect
- **Target Groups**: HTTP health checks (/health endpoint)
- **WebSocket Support**: Sticky sessions for WebSocket connections
- **SSL/TLS**: Self-signed certificate (production should use ACM)
- **CloudWatch Alarms**: Response time, unhealthy hosts, 5XX errors

### 5. **Monitoring** (`main.tf`)
- **CloudTrail**: Audit logging of all AWS API calls
- **CloudWatch Logs**: ECS, RDS, Redis, ALB logs
- **CloudWatch Alarms**: Automated alerting for performance/health issues

## Prerequisites

### Required Tools
```bash
# Install Terraform (v1.0+)
# https://www.terraform.io/downloads.html

# Install AWS CLI
# https://aws.amazon.com/cli/

# AWS Credentials configured
aws configure
```

### AWS Setup
```bash
# 1. Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket drishti-terraform-state \
  --region us-east-1

# 2. Enable versioning
aws s3api put-bucket-versioning \
  --bucket drishti-terraform-state \
  --versioning-configuration Status=Enabled

# 3. Enable encryption
aws s3api put-bucket-encryption \
  --bucket drishti-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# 4. Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name drishti-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Deployment

### 1. Initialize Terraform
```bash
cd terraform

# Initialize with S3 backend
terraform init \
  -backend-config="bucket=drishti-terraform-state" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true" \
  -backend-config="dynamodb_table=drishti-tfstate-lock"
```

### 2. Plan Deployment
```bash
# Staging environment
terraform plan \
  -var-file="staging.tfvars" \
  -var="db_username=postgres" \
  -var="db_password=YourSecurePasswordHere" \
  -out=tfplan

# Production environment
terraform plan \
  -var-file="prod.tfvars" \
  -var="db_username=postgres" \
  -var="db_password=YourSecurePasswordHere" \
  -out=tfplan
```

### 3. Apply Deployment
```bash
terraform apply tfplan
```

### 4. Retrieve Outputs
```bash
terraform output -json > infrastructure-info.json

# Get specific outputs
terraform output alb_dns_name
terraform output rds_endpoint
terraform output redis_endpoint
```

## Environment Variables

### Database Credentials
**IMPORTANT**: Use AWS Secrets Manager or environment variables, NOT in tfvars

```bash
# Export before terraform apply
export TF_VAR_db_username="postgres"
export TF_VAR_db_password="$(pwgen -s 32 1)"
```

### Container Image
```bash
# Override container image
terraform apply \
  -var="container_image=ghcr.io/drishti-ai/drishti-backend:v1.0.0"
```

## Configuration Files

- `variables.tf` - Input variables with validation
- `prod.tfvars` - Production environment variables
- `staging.tfvars` - Staging environment variables
- `backend-config.hcl` - S3 backend configuration
- `.terraform.lock.hcl` - Provider version locking

## File Structure

```
terraform/
├── main.tf                  # AWS provider, CloudTrail
├── networking.tf           # VPC, Subnets, NAT, Security Groups
├── compute.tf              # ECS Cluster, Task Definitions, Services
├── database.tf             # RDS, Redis, Secrets Manager
├── loadbalancer.tf         # ALB, Target Groups, Health Checks
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── prod.tfvars            # Production configuration
├── staging.tfvars         # Staging configuration
├── backend-config.hcl     # S3 backend config
└── .terraform.lock.hcl    # Provider locks
```

## Key Features

### High Availability
- ✅ Multi-AZ deployment
- ✅ Auto-scaling ECS tasks
- ✅ RDS Multi-AZ with failover
- ✅ Redis multi-node cluster
- ✅ Load balancing across AZs

### Security
- ✅ Encryption at rest (KMS)
- ✅ Encryption in transit (TLS)
- ✅ Secrets Manager for credentials
- ✅ Restricted security groups
- ✅ CloudTrail audit logging
- ✅ VPC isolation
- ✅ No public RDS/Redis access

### Monitoring & Observability
- ✅ CloudWatch Logs integration
- ✅ CloudWatch Alarms (CPU, memory, errors)
- ✅ CloudTrail audit trails
- ✅ ALB health checks
- ✅ ECS task monitoring
- ✅ RDS enhanced monitoring
- ✅ Redis slow log tracking

### Disaster Recovery
- ✅ Automated RDS backups (7-30 days)
- ✅ Redis snapshot backups (production)
- ✅ Multi-AZ failure tolerance
- ✅ Automatic task replacement
- ✅ Blue-green deployment capability

## Maintenance

### Scaling Configuration
```bash
# Update auto-scaling parameters
terraform apply \
  -var="ecs_min_capacity=3" \
  -var="ecs_max_capacity=20"
```

### Database Backup
```bash
# Create manual backup
aws rds create-db-snapshot \
  --db-instance-identifier drishti-db-production \
  --db-snapshot-identifier drishti-db-backup-$(date +%Y%m%d)
```

### Update Container Image
```bash
# Update ECS task definition
terraform apply \
  -var="container_image=ghcr.io/drishti-ai/drishti-backend:v1.2.0"

# Force ECS service update
aws ecs update-service \
  --cluster drishti-cluster-production \
  --service drishti-service \
  --force-new-deployment
```

## Troubleshooting

### Terraform State Issues
```bash
# Refresh state
terraform refresh -var-file="prod.tfvars"

# View state
terraform show

# Manually edit state (DANGEROUS!)
terraform state list
terraform state show 'aws_ecs_service.app'
```

### CloudFormation Stack Delete
```bash
# If resources are stuck in DELETE_IN_PROGRESS
aws cloudformation delete-stack --stack-name drishti-stack
```

### Check ECS Task Logs
```bash
# View logs from failed deployment
aws logs tail /ecs/drishti --follow
```

## Cost Optimization

### Staging Environment
- Use `db.t3.micro` (RDS)
- Use `cache.t3.micro` (Redis)
- Single-node Redis (no multi-AZ)
- Min 2 ECS tasks (no high availability)
- Smaller ALB

### Production Environment
- Use `db.t3.large` (RDS)
- Use `cache.t3.small` (Redis)
- Multi-AZ deployment
- 3-10 ECS tasks with auto-scaling
- Reserved Instances recommended

## Security Best Practices

1. **Rotate DB Credentials**: Change every 90 days
2. **Use AWS Secrets Manager**: Never commit credentials to Git
3. **Enable MFA**: Require MFA for AWS console access
4. **Review CloudTrail Logs**: Monthly audit of API calls
5. **Enable S3 Bucket Versioning**: For state file protection
6. **Backup Testing**: Regularly test RDS backup restoration
7. **Security Groups**: Review and update inbound rules quarterly

## References

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)
- [AWS RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)

## Support

For issues or questions:
1. Check CloudTrail logs: `aws logs tail /aws/cloudtrail --follow`
2. Review ECS task logs: `aws logs tail /ecs/drishti --follow`
3. Check Terraform plan output: `terraform plan -var-file="prod.tfvars"`
4. Validate syntax: `terraform validate`
