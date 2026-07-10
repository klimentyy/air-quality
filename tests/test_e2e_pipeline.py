import os
import io
import pytest
import polars as pl
import boto3
from moto import mock_aws
from unittest.mock import patch

from air_quality.config import AppConfig
from air_quality.main import main

@pytest.fixture
def mock_golemio_geojson():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [14.380116, 50.084385]},
                "properties": {
                    "id": "ABREA",
                    "name": "Praha 6-Břevnov",
                    "district": "praha-6",
                    "updated_at": "2026-07-09T15:45:00.448Z",
                    "measurement": {
                        "AQ_hourly_index": "2A",
                        "components": [
                            {"type": "NO2", "averaged_time": {"averaged_hours": "3", "value": 6.6}},
                            {"type": "PM10", "averaged_time": {"averaged_hours": "3", "value": 6.9}}
                        ]
                    }
                }
            }
        ]
    }


@mock_aws
@patch("httpx.Client.get")
def test_pipeline_e2e_lambda_s3_flow(mock_http_get, mock_golemio_geojson):
    """"""
    
    mock_response = mock_http_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = mock_golemio_geojson

    bucket_name = "prague-air-quality-data-lake-test"
    
    env_mock = {
        "AWS_LAMBDA_FUNCTION_NAME": "test_etl_function",
        "ENV": "test",
        "GOLEMIO_API_TOKEN": "valid_test_token",
        "DATA_HEALTH_BUCKET_NAME": bucket_name,
        "ALLOW_LOCAL_CLOUD_WRITE": "false"
    }

    with patch.dict(os.environ, env_mock, clear=True):
        AppConfig.ENV = os.environ["ENV"].lower()
        AppConfig.IS_LAMBDA = True
        AppConfig.ALLOW_CLOUD_WRITE = True
        AppConfig.GOLEMIO_API_TOKEN = os.environ["GOLEMIO_API_TOKEN"]
        AppConfig.BUCKET_NAME = os.environ["DATA_HEALTH_BUCKET_NAME"]

        s3_client = boto3.client("s3", region_name="eu-north-1")
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"}
        )

        main(event={}, context={})

        response = s3_client.get_object(Bucket=bucket_name, Key=AppConfig.S3_TARGET_KEY)
        parquet_bytes = response["Body"].read()
        
        df_result = pl.read_parquet(io.BytesIO(parquet_bytes))

        assert df_result.height == 1
        assert df_result.width == 8
        assert "NO2" in df_result.columns
        assert "PM10" in df_result.columns
        assert df_result["station_name"][0] == "Praha 6-Břevnov"
        assert df_result["NO2"][0] == 6.6
        assert df_result["PM10"][0] == 6.9



@patch("httpx.Client.get")
def test_pipeline_e2e_local_file_flow(mock_http_get, mock_golemio_geojson, tmp_path):
    
    mock_response = mock_http_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = mock_golemio_geojson

    local_output_file = str(tmp_path / "air_quality_latest.parquet")

    env_mock = {
        "ENV": "dev",
        "GOLEMIO_API_TOKEN": "local_dev_token",
        "ALLOW_LOCAL_CLOUD_WRITE": "false"
    }

    with patch.dict(os.environ, env_mock, clear=True):
        AppConfig.ENV = "dev"
        AppConfig.IS_LAMBDA = False
        AppConfig.ALLOW_CLOUD_WRITE = False
        AppConfig.GOLEMIO_API_TOKEN = os.environ["GOLEMIO_API_TOKEN"]
        AppConfig.LOCAL_TARGET_PATH = local_output_file

        os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
        
        main()

        assert os.path.exists(local_output_file)
        
        df_local = pl.read_parquet(local_output_file)
        assert df_local.height == 1
        assert df_local.width == 8
        assert df_local["NO2"].to_list() == [6.6]
        assert df_local["PM10"].to_list() == [6.9]