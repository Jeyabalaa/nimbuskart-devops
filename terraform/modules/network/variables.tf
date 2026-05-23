variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "project" {
  description = "Project name tag"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g. staging, prod)"
  type        = string
}

variable "owner" {
  description = "Team or person owning these resources"
  type        = string
}

variable "subnet_cidrs" {
  description = "List of two public subnet CIDRs"
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "availability_zones" {
  description = "List of two AZs for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}
