# Lambda assume role
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Scanner role
resource "aws_iam_role" "scanner_role" {
  name               = "${local.prefix}-scanner-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "scanner_policy" {
  name = "${local.prefix}-scanner-policy"
  role = aws_iam_role.scanner_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "s3:ListBucket",
          "s3:PutObject",
          "s3:GetBucketLocation",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "cloudwatch:PutMetricData"
        ],
        Effect   = "Allow",
        Resource = "*"
      }
    ]
  })
}

# Action role
resource "aws_iam_role" "action_role" {
  name               = "${local.prefix}-action-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "action_policy" {
  name = "${local.prefix}-action-policy"
  role = aws_iam_role.action_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "ec2:StopInstances",
          "ec2:DescribeInstances",
          "ec2:CreateTags",
          "s3:PutBucketTagging",
          "s3:PutObject",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "cloudwatch:PutMetricData"
        ],
        Effect   = "Allow",
        Resource = "*"
      }
    ]
  })
}

# AI-Insights role (includes bedrock invoke permissions)
resource "aws_iam_role" "ai_role" {
  name               = "${local.prefix}-ai-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "ai_policy" {
  name = "${local.prefix}-ai-policy"
  role = aws_iam_role.ai_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "S3DynamoSNS",
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "sns:Publish",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "cloudwatch:PutMetricData"
        ],
        Resource = "*"
      },
      {
        Sid    = "BedrockInvoke",
        Effect = "Allow",
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelAsync"
        ],
        Resource = "*"
      }
    ]
  })
}
