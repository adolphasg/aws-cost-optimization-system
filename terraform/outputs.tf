output "scanner_lambda_arn" {
  value = aws_lambda_function.scanner.arn
}
output "action_lambda_arn" {
  value = aws_lambda_function.action.arn
}
output "ai_lambda_arn" {
  value = aws_lambda_function.ai.arn
}
