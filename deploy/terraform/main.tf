# ⚠️ Aspirational — not applied. See deploy/terraform/README.md.
#
# Minimal single-VM deployment sketch for the FOI Deadline Tracker:
#   - EC2 instance running Docker
#   - EBS volume for /data (SQLite)
#   - S3 bucket for off-site backups
#   - Route 53 A record
#   - IAM role limited to writing the backup bucket
#
# This module HAS NOT been applied. Missing pieces called out in the README.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

locals {
  common_tags = merge(
    {
      Name       = var.name
      System     = "foi-tracker"
      Managed_by = "terraform"
    },
    var.tags,
  )
}

# -----------------------------------------------------------------------------
# Network — falls back to the account's default VPC/subnet if none provided.
# -----------------------------------------------------------------------------

data "aws_vpc" "target" {
  id      = var.vpc_id
  default = var.vpc_id == null ? true : null
}

data "aws_subnets" "target" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.target.id]
  }
}

resource "aws_security_group" "app" {
  name        = "${var.name}-app"
  description = "FOI Deadline Tracker — HTTP in from ALB, egress anywhere"
  vpc_id      = data.aws_vpc.target.id
  tags        = local.common_tags

  # Inbound HTTP from the VPC (in a real deployment, restrict to the ALB SG).
  ingress {
    description = "HTTP from VPC"
    from_port   = 5002
    to_port     = 5002
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.target.cidr_block]
  }

  egress {
    description = "All outbound (package updates, GOV.UK bank holidays API, S3)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# -----------------------------------------------------------------------------
# S3 backup bucket — versioning + lifecycle. Object-lock (WORM) would be added
# for a real deployment; see README.
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "backups" {
  bucket = "${var.name}-backups-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-daily-backups"
    status = "Enabled"

    filter {
      prefix = "daily/"
    }

    expiration {
      days = 14
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "expire-old-weekly-backups"
    status = "Enabled"

    filter {
      prefix = "weekly/"
    }

    expiration {
      days = 56 # 8 weeks
    }
  }
}

# -----------------------------------------------------------------------------
# IAM — instance role can write ONLY to the backup bucket. No other perms.
# -----------------------------------------------------------------------------

resource "aws_iam_role" "app" {
  name               = "${var.name}-app"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "backup_write" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
  }
}

resource "aws_iam_role_policy" "backup_write" {
  role   = aws_iam_role.app.id
  name   = "${var.name}-backup-write"
  policy = data.aws_iam_policy_document.backup_write.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.name}-app"
  role = aws_iam_role.app.name
}

# -----------------------------------------------------------------------------
# EC2 + EBS
# -----------------------------------------------------------------------------

data "aws_ami" "debian" {
  most_recent = true
  owners      = ["136693071363"] # Debian project

  filter {
    name   = "name"
    values = ["debian-12-amd64-*"]
  }
}

resource "aws_ebs_volume" "data" {
  availability_zone = data.aws_subnets.target.ids[0] # simplification — real deploy uses AZ from subnet
  size              = var.data_volume_size_gb
  type              = "gp3"
  encrypted         = true
  tags              = local.common_tags
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.debian.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id != null ? var.subnet_id : data.aws_subnets.target.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail
    apt-get update -y
    apt-get install -y docker.io docker-compose git
    # Real deployment pulls the container from ECR; here we assume the image
    # has been built and tagged locally, or that a CI pipeline pushes it.
    mkdir -p /data
    # (mount /dev/xvdf → /data would go here — see README for the sketch)
  EOF

  tags = local.common_tags

  lifecycle {
    ignore_changes = [ami] # AMI updates should be a deliberate replacement
  }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.app.id
}

# -----------------------------------------------------------------------------
# DNS (optional — only if a hosted zone id is provided)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "app" {
  count   = var.dns_zone_id != null ? 1 : 0
  zone_id = var.dns_zone_id
  name    = var.dns_name
  type    = "A"
  ttl     = 300
  records = [aws_instance.app.public_ip]
}
