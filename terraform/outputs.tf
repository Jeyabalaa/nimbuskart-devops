output "vpc_id" {
  description = "VPC ID for the NimbusKart staging environment"
  value       = module.network.vpc_id
}

output "subnet_ids" {
  description = "Public subnet IDs (one per AZ)"
  value       = module.network.subnet_ids
}

output "bucket_name" {
  description = "S3 bucket name for application logs"
  value       = aws_s3_bucket.app_logs.id
}

output "web_instance_ids" {
  description = "EC2 instance IDs for the web tier"
  value       = aws_instance.web[*].id
}

output "orphan_ebs_volume_id" {
  description = "ID of the intentionally unattached EBS volume (used in Part B testing)"
  value       = aws_ebs_volume.orphan.id
}
