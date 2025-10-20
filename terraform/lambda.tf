# Lambda image functions
resource "aws_lambda_function" "scanner" {
  function_name = "${local.prefix}-scanner"
  package_type  = "Image"
  image_uri     = var.scanner_image_uri
  role          = aws_iam_role.scanner_role.arn
  timeout       = 900
  environment {
    variables = {
      ENV             = var.env
      REPORT_BUCKET   = aws_s3_bucket.reports.bucket
      DDB_TABLE       = aws_dynamodb_table.cost.name
      CPU_THRESHOLD   = "5.0"
      CPU_WINDOW_DAYS = "7"
      S3_EMPTY_DAYS   = "30"
      AWS_REGION      = var.aws_region
    }
  }
}

resource "aws_lambda_function" "action" {
  function_name = "${local.prefix}-action"
  package_type  = "Image"
  image_uri     = var.action_image_uri
  role          = aws_iam_role.action_role.arn
  timeout       = 900
  environment {
    variables = {
      ENV           = var.env
      REPORT_BUCKET = aws_s3_bucket.reports.bucket
      DDB_TABLE     = aws_dynamodb_table.cost.name
      DRY_RUN       = "true"
      AWS_REGION    = var.aws_region
    }
  }
}

resource "aws_lambda_function" "ai" {
  function_name = "${local.prefix}-ai"
  package_type  = "Image"
  image_uri     = var.ai_image_uri
  role          = aws_iam_role.ai_role.arn
  timeout       = 900
  environment {
    variables = {
      ENV              = var.env
      REPORT_BUCKET    = aws_s3_bucket.reports.bucket
      DDB_TABLE        = aws_dynamodb_table.cost.name
      AI_SNS_TOPIC_ARN = aws_sns_topic.ai_summaries.arn
      MODEL_ID         = var.bedrock_model_id
      SUMMARY_TOP_N    = "5"
      AWS_REGION       = var.aws_region
    }
  }
}

# EventBridge target + permission for scanner
resource "aws_cloudwatch_event_target" "scanner_target" {
  rule      = aws_cloudwatch_event_rule.daily_scan.name
  target_id = "ScannerLambdaTarget"
  arn       = aws_lambda_function.scanner.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_scan.arn
}
