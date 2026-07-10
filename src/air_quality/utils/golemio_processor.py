import polars as pl
from typing import Any

def process_air_quality_data(raw_json: dict[str, Any]) -> pl.DataFrame:
    features = raw_json.get("features", [])
    if not features:
        return pl.DataFrame()

    df_raw = pl.DataFrame(features, strict=False)

    df_flat = df_raw.select(
        [
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("properties").struct.field("id").alias("station_id"),
            pl.col("properties").struct.field("name").alias("station_name"),
            pl.col("properties").struct.field("district").alias("district"),
            pl.col("properties").struct.field("updated_at").alias("updated_at_raw"),
            pl.col("properties").struct.field("measurement").struct.field("components").alias("components"),
        ]
    )

    df_exploded = df_flat.explode("components", empty_as_null=True)
    
    df_final = df_exploded.select([
        "station_id",
        "station_name",
        "district",
        "longitude",
        "latitude",
        pl.col("updated_at_raw").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.3fZ", strict=False).alias("updated_at"),
        pl.col("components").struct.field("type").alias("component_type"),
        pl.col("components").struct.field("averaged_time").struct.field("value").cast(pl.Float64, strict=False).alias("component_value")
    ])
    
    return df_final.pivot(
    on="component_type",
    index=["station_id", "station_name", "district", "longitude", "latitude", "updated_at"],
    values="component_value"
)