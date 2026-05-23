variable "region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name used in tags and resource names"
  type        = string
  default     = "nimbuskart"
}

variable "environment" {
  description = "Deployment environment (staging, prod, etc.)"
  type        = string
  default     = "staging"
}

variable "owner" {
  description = "Team or individual responsible for these resources"
  type        = string
  default     = "devops-team"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "subnet_cidrs" {
  description = "Two public subnet CIDRs"
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "availability_zones" {
  description = "Two availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "ami_id" {
  description = "AMI ID for EC2 instances (LocalStack accepts any string)"
  type        = string
  default     = "ami-0c02fb55956c7d316"
}

variable "instance_type" {
  description = "EC2 instance type for web tier"
  type        = string
  default     = "t3.micro"
}

# DEVIATION: Default restricted to a private range rather than 0.0.0.0/0.
# See README > Decisions & deviations for explanation.
variable "ssh_allowed_cidr" {
  description = "CIDR allowed for SSH (port 22). NEVER use 0.0.0.0/0 in production."
  type        = string
  default     = "10.0.0.0/8"
}

variable "log_bucket_name" {
  description = "Globally unique name for the S3 application-log bucket"
  type        = string
  default     = "nimbuskart-staging-app-logs"
}

variable "orphan_ebs_size_gb" {
  description = "Size (GB) of the intentionally unattached EBS volume used for Part B testing"
  type        = number
  default     = 10
}
