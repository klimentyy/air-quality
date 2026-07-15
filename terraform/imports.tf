# imports.tf

import {
  to = aws_s3_bucket.data_lake
  id = "prague-air-quality-project-data-lake-dev"
}

import {
  to = aws_iam_role.lambda_execution_role
  id = "air_quality_lambda_execution_role_dev"
}

import {
  to = aws_lambda_function.air_quality_etl
  id = "czech_air_quality_etl_dev"
}