################################################################################
# Compute - EC2 Instance (AWS Free Tier Compatible)
################################################################################

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# IAM Role for EC2
resource "aws_iam_role" "ec2_role" {
  name = "${var.app_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.app_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# Key Pair for SSH access
resource "aws_key_pair" "deploy_key" {
  key_name   = "${var.app_name}-deploy-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "app_server" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public_1.id
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name
  key_name             = aws_key_pair.deploy_key.key_name

  vpc_security_group_ids = [
    aws_security_group.ec2_sg.id
  ]

  user_data = <<-EOF
              #!/bin/bash
              set -e
              # Install Docker CE (official, includes compose plugin)
              apt-get update
              apt-get install -y ca-certificates curl gnupg
              install -m 0755 -d /etc/apt/keyrings
              curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
              chmod a+r /etc/apt/keyrings/docker.gpg
              echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list
              apt-get update
              apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
              systemctl enable docker
              systemctl start docker
              usermod -aG docker ubuntu
              # Setup app directory
              mkdir -p /home/ubuntu/drishti
              chown ubuntu:ubuntu /home/ubuntu/drishti
              EOF

  tags = {
    Name = "${var.app_name}-ec2-${var.environment}"
  }
}

resource "aws_eip" "app_eip" {
  instance = aws_instance.app_server.id
  domain   = "vpc"

  tags = {
    Name = "${var.app_name}-eip"
  }
}


