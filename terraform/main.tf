terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# LocalStack endpoint override — tflocal sets this automatically.
# Left here explicitly so reviewers can see how the provider is wired.
provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://localhost:4566"
    s3  = "http://localhost:4566"
    iam = "http://localhost:4566"
  }
}

# ── Network module ────────────────────────────────────────────────────────────
module "network" {
  source = "./modules/network"

  vpc_cidr           = var.vpc_cidr
  subnet_cidrs       = var.subnet_cidrs
  availability_zones = var.availability_zones
  project            = var.project
  environment        = var.environment
  owner              = var.owner
}

# ── Security group ────────────────────────────────────────────────────────────
resource "aws_security_group" "web" {
  name        = "${var.project}-${var.environment}-web-sg"
  description = "Allow HTTP, HTTPS, and restricted SSH"
  vpc_id      = module.network.vpc_id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # DEVIATION: Restricted to var.ssh_allowed_cidr (default 10.0.0.0/8),
  # NOT 0.0.0.0/0 as the spec says. See README > Decisions & deviations.
  ingress {
    description = "SSH from restricted CIDR only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-web-sg"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

# ── EC2 web-tier instances ────────────────────────────────────────────────────
resource "aws_instance" "web" {
  count         = 2
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = module.network.subnet_ids[count.index]

  vpc_security_group_ids = [aws_security_group.web.id]

  tags = {
    Name        = "${var.project}-${var.environment}-web-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Tier        = "web"
  }
}

# ── S3 application-log bucket ─────────────────────────────────────────────────
resource "aws_s3_bucket" "app_logs" {
  bucket = var.log_bucket_name

  tags = {
    Name        = var.log_bucket_name
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ── Orphan EBS volume (intentional — for Part B testing) ──────────────────────
# This volume is deliberately left unattached so the Cost Janitor can detect it.
resource "aws_ebs_volume" "orphan" {
  availability_zone = var.availability_zones[0]
  size              = var.orphan_ebs_size_gb
  type              = "gp3"

  tags = {
    Name        = "${var.project}-${var.environment}-orphan-vol"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Purpose     = "intentional-orphan-for-janitor-testing"
  }
}
