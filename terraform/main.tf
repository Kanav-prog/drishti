################################################################################
# Terraform Backend + Provider (Free Tier — S3 state, no CloudTrail)
################################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Partial backend — bucket name is injected via -backend-config in CI
  # (bucket name includes AWS account ID so it is globally unique)
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "DRISHTI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
