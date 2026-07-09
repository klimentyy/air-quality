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

resource "null_resource" "build_lambda" {
    triggers = {
        code_hash = md5(file("${path.module}/../src/air_quality/main.py"))
        requirements_hash = md5(file("${path.module}/../src/requirements.txt"))
  
}
    provisioner "local-exec" {
        command = "cd ${path.module}/.. && make build"
    }
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

resource "aws_lambda_function" "air_quality_etl" {
    filename = "${path.module}/../lambda_function.zip"
    function_name = "air_quiaity_etl"
    role = aws_iam_role.lambda_execution_role.arn
    handler = "air_quality.main.main"
    runtime = "python3.13"
    timeout = 60

    environment {
      variables = {
        GOLEMIO_API_TOKEN = var.golemio_api_token
      }
    }

    source_code_hash = filebase64sha256(data.local_file.lambda_zip.filename)

    depends_on = [ null_resource.build_lambda ]
  
}
