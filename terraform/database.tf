################################################################################
# Database - RDS PostgreSQL (Free Tier Eligible)
################################################################################

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.app_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name = "${var.app_name}-db-subnet-group"
  }
}

# RDS PostgreSQL Database (Free Tier Eligible db.t3.micro)
resource "aws_db_instance" "app" {
  identifier              = "${var.app_name}-db-${var.environment}"
  allocated_storage       = 20
  storage_type            = "gp3"
  engine                  = "postgres"
  engine_version          = var.rds_engine_version
  instance_class          = "db.t3.micro"
  db_name                 = "drishti_db"
  username                = var.db_username
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  skip_final_snapshot     = true
  publicly_accessible     = false

  multi_az = false
  deletion_protection = false

  tags = {
    Name = "${var.app_name}-db-${var.environment}"
  }
}

# Database Secrets (for connection string)
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.app_name}/database-url"

  tags = {
    Name = "${var.app_name}-database-url"
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.app.endpoint}/${aws_db_instance.app.db_name}?sslmode=require"
}
