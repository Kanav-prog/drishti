# Terraform Backend Configuration for S3
# Usage: terraform init -backend-config=terraform/backend-config.hcl

bucket         = "drishti-terraform-state"
key            = "terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "drishti-tfstate-lock"
