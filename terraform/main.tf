terraform {
    required_version = ">= 1.5.8"
    required_providers{
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }
    }
}
provider "aws" {
    region = var.aws_region
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
    bucket = "air-quality-project-data-lake-klimentyyy"
}

resource "aws_iam_role" "lambda_execution_role" {
  name = "air_quality_lambda_execution_role"

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
    name = "lambda_iam_role_policy"
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

resource "aws_lambda_layer_version" "lib_layer" {
    filename = "${path.module}/../python_layer.zip"
    layer_name = "air_quality_dependencies"
    compatible_runtimes = [ "python3.13" ]

    source_code_hash = filemd5("${path.module}/../python_layer.zip")
}

data "archive_file" "code_zip" {
    type        = "zip"
    source_dir  = "${path.module}/../src"
    output_path = "${path.module}/../code_function.zip"
}

resource "aws_lambda_function" "air_quality_etl" {
    filename         = data.archive_file.code_zip.output_path
    function_name    = "czech_air_quality_etl"
    role             = aws_iam_role.lambda_execution_role.arn
    handler          = "air_quality.main.main"
    runtime          = "python3.13"
    timeout          = 60

    layers = [ aws_lambda_layer_version.lib_layer.arn ]

    environment {
        variables = {
        GOLEMIO_API_TOKEN = var.golemio_api_token
        }
    }

    source_code_hash = data.archive_file.code_zip.output_base64sha256

  
}

resource "aws_cloudwatch_event_rule" "air_quality_hourly_cron" {
    name = "air-quality-collect-hourly-cron"
    description         = "Triggers the Czech Air Quality ETL Lambda function every hour"
    schedule_expression = "cron(0 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "air_quality_lambda_target" {
    rule = aws_cloudwatch_event_rule.air_quality_hourly_cron.name
    target_id = "TriggerAirQualityLambda"
    arn = aws_lambda_function.air_quality_etl.arn
}

resource "aws_lambda_permission" "allow_eventbridge_to_invoke_lambda" {
  statement_id = "AllowExecutionFromEventBridge"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.air_quality_etl.function_name
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.air_quality_hourly_cron.arn
}