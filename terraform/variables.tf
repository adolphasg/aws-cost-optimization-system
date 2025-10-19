variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "cost-optimizer"
}

variable "env" {
  description = "Environment name (staging or prod)"
  type        = string
  default     = "staging"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account id"
  type        = string
  default     = ""
}

variable "scanner_image_uri" {
  description = "ECR image URI for scanner lambda"
  type        = string
  default     = ""
}

variable "action_image_uri" {
  description = "ECR image URI for action lambda"
  type        = string
  default     = ""
}

variable "ai_image_uri" {
  description = "ECR image URI for ai insights lambda"
  type        = string
  default     = ""
}

variable "bedrock_model_id" {
  description = "Bedrock model ID to call from AI lambda (on-demand)"
  type        = string
  default     = ""
}
