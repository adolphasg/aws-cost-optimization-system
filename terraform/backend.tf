terraform {
  backend "s3" {
    bucket         = "levelup-tfstate-bucket-adolphasg"
    key            = "cost-optimizer/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "levelup-tfstate-lock"
    encrypt        = true
  }
}