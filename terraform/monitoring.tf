# CloudWatch alarm for > 5 idle EC2 instances in a single scan
resource "aws_cloudwatch_metric_alarm" "many_idle_ec2" {
  alarm_name          = "${local.prefix}-idle-ec2-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "IdleResources.Count"
  namespace           = "CostOptimizer"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alarm when idle EC2 count exceeds 5 for this env"
  alarm_actions       = [aws_sns_topic.ai_summaries.arn]
  dimensions = {
    Env          = var.env
    ResourceType = "ec2"
  }
}

# Basic dashboard to visualize key numbers
resource "aws_cloudwatch_dashboard" "dashboard" {
  dashboard_name = "${local.prefix}-dashboard"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric",
        x    = 0, y = 0, width = 12, height = 6,
        properties = {
          title   = "Idle EC2 Count",
          view    = "timeSeries",
          stacked = false,
          metrics = [
            ["CostOptimizer", "IdleResources.Count", "Env", var.env, "ResourceType", "ec2"]
          ],
          region = var.aws_region,
          period = 300
        }
      },
      {
        type = "metric",
        x    = 12, y = 0, width = 12, height = 6,
        properties = {
          title = "Estimated Savings (USD)",
          view  = "timeSeries",
          metrics = [
            ["CostOptimizer", "EstimatedSavings.MonthlyUSD", "Env", var.env]
          ],
          region = var.aws_region,
          period = 300
        }
      },
      {
        type = "text",
        x    = 0, y = 6, width = 24, height = 3,
        properties = {
          markdown = "### Top recent run\nCheck S3 reports under the bucket for run JSONs"
        }
      }
    ]
  })
}
