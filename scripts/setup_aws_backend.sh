#!/bin/bash
# setup_aws_backend.sh
# Creates the S3 bucket and DynamoDB table for Terraform remote state.
# Bucket name is unique per AWS account: drishti-tfstate-<account-id>
set -e

REGION="us-east-1"
TABLE_NAME="drishti-tfstate-lock"

# Get AWS account ID dynamically so bucket name is globally unique
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="drishti-tfstate-${ACCOUNT_ID}"

# Export so the calling script (CI) can read it
echo "TF_STATE_BUCKET=${BUCKET_NAME}" >> "${GITHUB_ENV:-/dev/null}"
echo "Using S3 bucket: ${BUCKET_NAME}"

# ── S3 Bucket ────────────────────────────────────────────────────────────────
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "✅ Bucket ${BUCKET_NAME} already exists."
else
  echo "Creating S3 bucket: ${BUCKET_NAME} in region ${REGION}"
  aws s3api create-bucket \
    --bucket "${BUCKET_NAME}" \
    --region "${REGION}"
fi

echo "Enabling versioning..."
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

echo "Enabling encryption..."
aws s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

echo "Blocking public access..."
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ── DynamoDB Lock Table ───────────────────────────────────────────────────────
if aws dynamodb describe-table --table-name "${TABLE_NAME}" --region "${REGION}" 2>/dev/null; then
  echo "✅ DynamoDB table ${TABLE_NAME} already exists."
else
  echo "Creating DynamoDB table: ${TABLE_NAME}"
  aws dynamodb create-table \
    --table-name "${TABLE_NAME}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}"
fi

echo "✅ AWS Backend setup complete! Bucket: ${BUCKET_NAME}"
