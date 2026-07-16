# ⚠️ Aspirational — not applied. See deploy/terraform/README.md.

variable "name" {
  description = "Name tag applied to every resource."
  type        = string
  default     = "foi-tracker"
}

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2" # London — most likely for DfT
}

variable "vpc_id" {
  description = "Existing VPC to deploy into. Defaults to the account's default VPC."
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "Existing subnet for the EC2 instance."
  type        = string
  default     = null
}

variable "instance_type" {
  description = "EC2 instance size."
  type        = string
  default     = "t3.small"
}

variable "data_volume_size_gb" {
  description = "EBS volume size for /data."
  type        = number
  default     = 10
}

variable "dns_zone_id" {
  description = "Route 53 hosted zone to create a record in. Leave null to skip DNS."
  type        = string
  default     = null
}

variable "dns_name" {
  description = "Fully-qualified DNS name for the service."
  type        = string
  default     = null
}

variable "tags" {
  description = "Additional tags applied to every taggable resource."
  type        = map(string)
  default     = {}
}
