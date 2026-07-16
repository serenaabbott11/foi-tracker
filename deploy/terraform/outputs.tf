# ⚠️ Aspirational — not applied. See deploy/terraform/README.md.

output "instance_public_ip" {
  description = "Public IP of the EC2 instance (only useful once inside the VPC or via a bastion)."
  value       = aws_instance.app.public_ip
}

output "backups_bucket" {
  description = "S3 bucket name to use for backup uploads."
  value       = aws_s3_bucket.backups.bucket
}

output "dns_name" {
  description = "Route 53 record, if a hosted zone was provided."
  value       = length(aws_route53_record.app) > 0 ? aws_route53_record.app[0].fqdn : null
}
