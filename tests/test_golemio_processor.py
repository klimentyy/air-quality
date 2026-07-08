import pytest
import polars as pl
from src.air_quality.utils.golemio_processor import process_air_quality_data

@pytest.fixture
def sample_golemio_json():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [14.380116, 50.084385]
                },
                "properties": {
                    "id": "ABREA",
                    "name": "Praha 6-Břevnov",
                    "district": "praha-6",
                    "updated_at": "2026-07-08T08:15:00.000Z",
                    "measurement": {
                        "AQ_hourly_index": "1B",
                        "components": [
                            {
                                "type": "NO2",
                                "averaged_time": {"value": 10.5}  # Float64
                            },
                            {
                                "type": "PM10",
                                "averaged_time": {"value": 4}     # Int64
                            }
                        ]
                    }
                }
            }
        ]
    }

def test_process_air_quality_data_success(sample_golemio_json):
    # Act
    result_df = process_air_quality_data(sample_golemio_json)
    
    # Assert
    assert isinstance(result_df, pl.DataFrame)
    assert not result_df.is_empty()
    
    expected_columns = ["station_id", "station_name", "district", "longitude", "latitude", "updated_at", "NO2", "PM10"]
    for col in expected_columns:
        assert col in result_df.columns

    row = result_df.filter(pl.col("station_id") == "ABREA")
    assert row["station_name"][0] == "Praha 6-Břevnov"
    assert row["longitude"][0] == 14.380116
    assert row["latitude"][0] == 50.084385
    
    assert row["NO2"][0] == 10.5
    assert row["PM10"][0] == 4.0
    assert result_df["NO2"].dtype == pl.Float64
    assert result_df["PM10"].dtype == pl.Float64

def test_process_air_quality_data_empty():
    empty_json = {"features": []}
    result_df = process_air_quality_data(empty_json)
    
    assert isinstance(result_df, pl.DataFrame)
    assert result_df.is_empty()