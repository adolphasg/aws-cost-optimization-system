locals {
  prefix = "${var.project_name}-${var.env}"
}

# Create the bucket
resource "aws_s3_bucket" "reports" {
  bucket = "levelup-reports-bucket-2025-09-21"
}

# Attach encryption config separately
resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_public_access_block" "reports_block" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# DynamoDB table
resource "aws_dynamodb_table" "cost" {
  name         = "${local.prefix}-history"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "resource_id"
    type = "S"
  }

  global_secondary_index {
    name            = "resource-index"
    hash_key        = "resource_id"
    projection_type = "ALL"
  }

  tags = {
    Project = var.project_name
    Env     = var.env
  }
}

# SNS topic for AI summaries + alarm notifications
resource "aws_sns_topic" "ai_summaries" {
  name = "${local.prefix}-ai-summaries"
}

# Create ECR repositories for lambda images
resource "aws_ecr_repository" "scanner" {
  name = "${local.prefix}-scanner"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "action" {
  name = "${local.prefix}-action"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "ai" {
  name = "${local.prefix}-ai"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# CloudWatch log group lifecycles are created automatically via Lambda creation

# EventBridge schedule rule (daily scan at 01:00 UTC by default)
resource "aws_cloudwatch_event_rule" "daily_scan" {
  name                = "${local.prefix}-daily-scan"
  schedule_expression = "rate(24 hours)"
  description         = "Daily scanner trigger"
}

# Provide outputs for the pipleine
output "reports_bucket" {
  value = aws_s3_bucket.reports.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.cost.name
}

output "ai_sns_topic_arn" {
  value = aws_sns_topic.ai_summaries.arn
}

output "ecr_scanner_repo" {
  value = aws_ecr_repository.scanner.repository_url
}
output "ecr_action_repo" {
  value = aws_ecr_repository.action.repository_url
}
output "ecr_ai_repo" {
  value = aws_ecr_repository.ai.repository_url
}
