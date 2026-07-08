import polars as pl
from typing import Any, Dict


def process_air_quality_data(raw_json: Dict[str, Any]) -> pl.DataFrame:
    """
    Processes raw JSON data from the Golemio API and converts it into a Polars DataFrame.

    Args:
        raw_json (Dict[str, Any]): The raw JSON data from the Golemio API.

    Returns:
        pl.DataFrame: A Polars DataFrame containing the processed air quality data.
    """
    features = raw_json.get("features", [])
    if not features:
        return pl.DataFrame()

    df_raw = pl.DataFrame(features, strict=False)

    df_flat = df_raw.select(
        [
            pl.col("geometry").struct.field("coordinates").get(0).alias("longitude"),
            pl.col("geometry").struct.field("coordinates").get(1).alias("latitude"),
            pl.col("properties").struct.field("id").alias("station_id"),
            pl.col("properties").struct.field("name").alias("station_name"),
            pl.col("properties").struct.field("district").alias("district"),
            pl.col("properties")
            .struct.field("updated_at")
            .str.to_datetime("%Y-%m-%dT%H:%M:%S%.3fZ", strict=False)
            .alias("updated_at"),
            pl.col("properties")
            .struct.field("measurement")
            .struct.field("components")
            .alias("components"),
        ]
    )

    df_components = df_flat.explode("components").with_columns(
        [
            pl.col("components").struct.field("type").alias("component_type"),
            pl.col("components")
            .struct.field("averaged_time")
            .struct.field("value")
            .cast(pl.Float64, strict=False)
            .alias("component_value"),
        ]
    )

    df_final = df_components.pivot(
        on="component_type",
        index=[
            "station_id",
            "station_name",
            "district",
            "longitude",
            "latitude",
            "updated_at",
        ],
        values="component_value",
    )

    return df_final
