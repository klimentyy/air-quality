terraform {
    required_version = ">= 1.5.8"
    required_providers{
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }
    }
    backend "s3" {
      bucket = "prague-air-quality-project-data-lake" 
      key    = "state/terraform.tfstate"                
      region = "eu-north-1"
  }
}
provider "aws" {
  region = var.aws_region
}

variable "environment" {
  type    = string
  description = "Deployment environment (dev or prod)"
  default = "dev"
}

variable "aws_region" {
  type = string
  default = "eu-north-1"
}

variable "golemio_api_token" {
  type = string
  sensitive = true
}

resource "aws_s3_bucket" "data_lake" {
  bucket        = "prague-air-quality-project-data-lake-${var.environment}"
  force_destroy = var.environment == "dev" ? true : false
}

resource "aws_iam_role" "lambda_execution_role" {
  name = "air_quality_lambda_execution_role_${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_execution_role" {
  name = "lambda_iam_role_policy_${var.environment}"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
      Version = "2012-10-17"
  Statement = [
    {
      Action = [
        "s3:PutObject",
        "s3:GetObject"
      ]
      Resource = "${aws_s3_bucket.data_lake.arn}/*"
      Effect   = "Allow"
    },
    {
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "arn:aws:logs:*:*:*"
      Effect = "Allow" 
    }
  ]
  })
}

resource "aws_s3_object" "lambda_layer_zip" {
  bucket      = aws_s3_bucket.data_lake.id
  key         = "layers/python_layer.zip"
  source      = "${path.module}/../python_layer.zip"
  
  source_hash = filemd5("${path.module}/../python_layer.zip")
}

resource "aws_lambda_layer_version" "lib_layer" {
  layer_name          = "air_quality_dependencies_${var.environment}"
  compatible_runtimes = ["python3.13"]

  s3_bucket           = aws_s3_bucket.data_lake.id
  s3_key              = aws_s3_object.lambda_layer_zip.key
  
  source_code_hash    = aws_s3_object.lambda_layer_zip.source_hash
}

data "archive_file" "code_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/../code_function.zip"
}

resource "aws_lambda_function" "air_quality_etl" {
  filename         = data.archive_file.code_zip.output_path
  function_name    = "czech_air_quality_etl_${var.environment}"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "air_quality.main.main"
  runtime          = "python3.13"
  timeout          = 60

  layers = [ aws_lambda_layer_version.lib_layer.arn ]

  environment {
      variables = {
        ENV                     = var.environment
        GOLEMIO_API_TOKEN = var.golemio_api_token
        DATA_HEALTH_BUCKET_NAME = aws_s3_bucket.data_lake.id
      }
  }

  source_code_hash = data.archive_file.code_zip.output_base64sha256
}

resource "aws_cloudwatch_event_rule" "air_quality_hourly_cron" {
  name = "air-quality-collect-hourly-cron-${var.environment}"
  description         = "Triggers the Czech Air Quality ETL Lambda function every hour"
  schedule_expression = "cron(0 * * * ? *)"

  lifecycle {
      create_before_destroy = true
    }
}

resource "aws_cloudwatch_event_target" "air_quality_lambda_target" {
  rule = aws_cloudwatch_event_rule.air_quality_hourly_cron.name
  target_id = "TriggerAirQualityLambda"
  arn = aws_lambda_function.air_quality_etl.arn

  lifecycle {
      create_before_destroy = true
    }
}

resource "aws_lambda_permission" "allow_eventbridge_to_invoke_lambda" {
  statement_id = "AllowExecutionFromEventBridge"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.air_quality_etl.function_name
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.air_quality_hourly_cron.arn
}

