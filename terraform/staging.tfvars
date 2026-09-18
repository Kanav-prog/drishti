aws_region       = "us-east-1"
environment      = "staging"
container_image  = "ghcr.io/drishti-ai/drishti-backend:develop"
container_port   = 8000

# ECS Configuration
ecs_desired_count = 2
ecs_min_capacity  = 2
ecs_max_capacity  = 5

# RDS Configuration
rds_allocated_storage = 20
rds_instance_class    = "db.t3.micro"
rds_engine_version    = "15.3"

# Redis Configuration
redis_node_type        = "cache.t3.micro"
redis_num_cache_nodes  = 1

# VPC Configuration
vpc_cidr = "10.0.0.0/16"

# Backup Configuration
enable_backup         = true
backup_retention_days = 7
