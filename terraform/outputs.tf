################################################################################
# Outputs
################################################################################

output "ec2_public_ip" {
  value       = aws_eip.app_eip.public_ip
  description = "Public IP of the DRISHTI EC2 instance — use as EC2_HOST secret"
}

output "rds_endpoint" {
  value       = aws_db_instance.app.endpoint
  description = "RDS database endpoint"
}

output "rds_address" {
  value       = aws_db_instance.app.address
  description = "RDS database address (hostname)"
}

output "rds_port" {
  value       = aws_db_instance.app.port
  description = "RDS port (5432)"
}

output "rds_database_name" {
  value       = aws_db_instance.app.db_name
  description = "RDS database name"
}

output "aws_region" {
  value       = var.aws_region
  description = "AWS Region"
}

output "environment" {
  value       = var.environment
  description = "Environment"
}

output "application_url" {
  value       = "http://${aws_eip.app_eip.public_ip}"
  description = "Application URL — copy this into browser to access DRISHTI"
}

output "infrastructure_summary" {
  description = "All key infrastructure details at a glance"
  value = {
    app_url      = "http://${aws_eip.app_eip.public_ip}"
    ec2_ip       = aws_eip.app_eip.public_ip
    rds_endpoint = aws_db_instance.app.endpoint
    environment  = var.environment
    region       = var.aws_region
  }
}
