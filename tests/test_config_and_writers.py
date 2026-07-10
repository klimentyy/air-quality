import os
import io
import pytest
import polars as pl
import boto3
from unittest.mock import MagicMock, patch
from moto import mock_aws

from air_quality.config import AppConfig
from air_quality.writers.writer import LocalFileWriter, S3Writer
from air_quality.main import run_pipeline
from air_quality.ingestors.base_client import BaseAirQualityClient


def test_app_config_validation_success():
    """Test validation passes with proper configuration."""
    with patch.dict(os.environ, {"GOLEMIO_API_TOKEN": "some_token", "DATA_HEALTH_BUCKET_NAME": "some_bucket"}):
        # Dynamically reload values since they are set at class import time
        AppConfig.GOLEMIO_API_TOKEN = "some_token"
        AppConfig.BUCKET_NAME = "some_bucket"
        AppConfig.ALLOW_CLOUD_WRITE = False
        AppConfig.ENV = "dev"
        
        # Should not raise any exception
        AppConfig.validate()


def test_app_config_validation_missing_token():
    """Test validation fails when GOLEMIO_API_TOKEN is missing."""
    AppConfig.GOLEMIO_API_TOKEN = ""
    AppConfig.BUCKET_NAME = "some_bucket"
    AppConfig.ALLOW_CLOUD_WRITE = False
    AppConfig.ENV = "dev"
    
    with pytest.raises(ValueError, match="CRITICAL: GOLEMIO_API_TOKEN is missing"):
        AppConfig.validate()


def test_app_config_validation_missing_bucket_cloud_write():
    """Test validation fails when cloud write is enabled but bucket name is missing."""
    AppConfig.GOLEMIO_API_TOKEN = "some_token"
    AppConfig.BUCKET_NAME = ""
    AppConfig.ALLOW_CLOUD_WRITE = True
    AppConfig.ENV = "dev"
    
    with pytest.raises(ValueError, match="CRITICAL: BUCKET_NAME is missing"):
        AppConfig.validate()


def test_app_config_validation_missing_bucket_non_dev():
    """Test validation fails when environment is non-dev and bucket name is missing."""
    AppConfig.GOLEMIO_API_TOKEN = "some_token"
    AppConfig.BUCKET_NAME = ""
    AppConfig.ALLOW_CLOUD_WRITE = False
    AppConfig.ENV = "production"
    
    with pytest.raises(ValueError, match="CRITICAL: BUCKET_NAME is missing"):
        AppConfig.validate()


def test_local_file_writer(tmp_path):
    """Test LocalFileWriter saves a parquet file correctly."""
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    target_file = tmp_path / "subdir" / "test.parquet"
    
    writer = LocalFileWriter()
    writer.write(df, str(target_file))
    
    assert target_file.exists()
    df_read = pl.read_parquet(target_file)
    assert df_read.equals(df)


@mock_aws
def test_s3_writer_success():
    """Test S3Writer uploads a parquet file to S3 correctly."""
    bucket_name = "test-air-quality-bucket"
    target_key = "test_data.parquet"
    
    # Set up S3 mock bucket
    s3_client = boto3.client("s3", region_name="eu-north-1")
    s3_client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "eu-north-1"}
    )
    
    df = pl.DataFrame({"x": [10, 20], "y": ["hello", "world"]})
    writer = S3Writer()
    
    with patch.dict(os.environ, {"DATA_HEALTH_BUCKET_NAME": bucket_name}):
        writer.write(df, target_key)
        
        # Verify the file was uploaded
        response = s3_client.get_object(Bucket=bucket_name, Key=target_key)
        content = response["Body"].read()
        
        df_read = pl.read_parquet(io.BytesIO(content))
        assert df_read.equals(df)


def test_s3_writer_missing_bucket_env():
    """Test S3Writer raises ValueError if DATA_HEALTH_BUCKET_NAME env variable is not set."""
    df = pl.DataFrame({"x": [10]})
    writer = S3Writer()
    
    with patch.dict(os.environ, {}, clear=True):
        if "DATA_HEALTH_BUCKET_NAME" in os.environ:
            del os.environ["DATA_HEALTH_BUCKET_NAME"]
            
        with pytest.raises(ValueError, match="DATA_HEALTH_BUCKET_NAME environment variable is not set"):
            writer.write(df, "dummy.parquet")


def test_run_pipeline_success():
    """Test run_pipeline calls the writer with correct parameters when DataFrame is not empty."""
    mock_client = MagicMock(spec=BaseAirQualityClient)
    mock_df = pl.DataFrame({"col": [1]})
    mock_client.get_cleaned_data.return_value = mock_df
    
    mock_writer = MagicMock(spec=LocalFileWriter)
    
    run_pipeline(client=mock_client, writer=mock_writer, target="test_target.parquet")
    
    mock_writer.write.assert_called_once_with(mock_df, "test_target.parquet")


def test_run_pipeline_empty_dataframe():
    """Test run_pipeline does not call writer when DataFrame is empty."""
    mock_client = MagicMock(spec=BaseAirQualityClient)
    mock_df = pl.DataFrame()
    mock_client.get_cleaned_data.return_value = mock_df
    
    mock_writer = MagicMock(spec=LocalFileWriter)
    
    run_pipeline(client=mock_client, writer=mock_writer, target="test_target.parquet")
    
    mock_writer.write.assert_not_called()


def test_run_pipeline_exception():
    """Test run_pipeline logs and propagates exceptions raised by client."""
    mock_client = MagicMock(spec=BaseAirQualityClient)
    mock_client.get_cleaned_data.side_effect = RuntimeError("API failure")
    
    mock_writer = MagicMock(spec=LocalFileWriter)
    
    with pytest.raises(RuntimeError, match="API failure"):
        run_pipeline(client=mock_client, writer=mock_writer, target="test_target.parquet")
