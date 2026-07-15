import io
import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import boto3
import streamlit as st
import polars as pl
import pydeck as pdk
import pandas as pd

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

src_path = str(Path(__file__).resolve().parents[1])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from air_quality.config import AppConfig # noqa: E402

STANDARD_COMPONENTS = [
    "station_id",
    "station_name",
    "district",
    "longitude",
    "latitude",
    "updated_at",
    "AQ_hourly_index",
]

RGBA_COLORS = {
    "green": [46, 204, 113, 200],
    "yellow": [241, 196, 15, 200],
    "red": [231, 76, 60, 200],
    "grey": [149, 165, 166, 150],
    "violet": [155, 89, 182, 160],
}


@st.cache_resource
def get_s3_resource():
    """Initialize the S3 client using Streamlit Secrets."""
    return boto3.client(
        "s3",  # type: ignore[arg-type]
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
        region_name=st.secrets["aws"].get("aws_region"),
    )


def load_data_from_s3(
    bucket_name: str = AppConfig.BUCKET_NAME, file_key: str = AppConfig.S3_TARGET_KEY
) -> pl.DataFrame:
    s3_client: "S3Client" = get_s3_resource()
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_bytes = response["Body"].read()

        return pl.read_parquet(io.BytesIO(file_bytes))
    except Exception as e:
        st.error(f"Failed to fetch data from S3: {e}")
        raise e


@st.cache_resource
def load_data_locally(file_path: Path) -> pl.DataFrame:
    """Load data from a Parquet file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.suffix == ".parquet":
        raise ValueError("File must be a Parquet file.")

    return pl.read_parquet(file_path)


def add_visual_data_to_aq_index(data: pl.DataFrame) -> pl.DataFrame:
    """Add a color column to the DataFrame based on AQ_hourly_index."""
    color_lookup = pl.DataFrame(
        {
            "AQ_hourly_index": ["1A", "2A", "0"],
            "color_r": [
                RGBA_COLORS["green"][0],
                RGBA_COLORS["yellow"][0],
                RGBA_COLORS["grey"][0],
            ],
            "color_g": [
                RGBA_COLORS["green"][1],
                RGBA_COLORS["yellow"][1],
                RGBA_COLORS["grey"][1],
            ],
            "color_b": [
                RGBA_COLORS["green"][2],
                RGBA_COLORS["yellow"][2],
                RGBA_COLORS["grey"][2],
            ],
        }
    )
    default = RGBA_COLORS["red"]
    return data.join(color_lookup, on="AQ_hourly_index", how="left").with_columns(
        [
            pl.col("color_r").fill_null(default[0]),
            pl.col("color_g").fill_null(default[1]),
            pl.col("color_b").fill_null(default[2]),
            pl.lit(255).alias("color_a"),
            pl.lit(200).alias("radius"),
        ]
    )


def add_visual_data_to_gas(data: pl.DataFrame, gas: str) -> pl.DataFrame:
    MIN_RADIUS = 200
    MAX_RADIUS = 2000
    default = RGBA_COLORS["violet"]

    gas_col = pl.col(gas)
    val_min = gas_col.min()
    val_max = gas_col.max()
    # Normalize the radius
    radius_expr = (
        pl.when(val_min == val_max)
        .then(MIN_RADIUS)
        .otherwise(
            MIN_RADIUS
            + ((gas_col - val_min) / (val_max - val_min)) * (MAX_RADIUS - MIN_RADIUS)
        )
    )

    return data.with_columns(
        pl.lit(default[0]).alias("color_r"),
        pl.lit(default[1]).alias("color_g"),
        pl.lit(default[2]).alias("color_b"),
        pl.lit(default[3]).alias("color_a"),
        radius_expr.alias("radius"),
    )


def create_dashboard(data: pl.DataFrame):
    """Create a Streamlit dashboard to visualize air quality data."""

    st.title("Air Quality Dashboard")
    st.write("This dashboard visualizes air quality data.")

    DISTRICT_OPTIONS = sorted(data["district"].unique().to_list())
    ALL_GASES = sorted(list(set(data.columns) - set(STANDARD_COMPONENTS)))
    NONE_OPTION = "Overall Index"

    with st.sidebar:
        st.header("Filters")

        selected_districts = st.multiselect(
            label="Select Districts", options=DISTRICT_OPTIONS, default=[]
        )
        selected_gas = st.selectbox(
            "Select Gas Type", options=[NONE_OPTION] + ALL_GASES
        )

    filtered_df = data
    if selected_districts:
        filtered_df = filtered_df.filter(pl.col("district").is_in(selected_districts))

    if selected_gas != NONE_OPTION:
        filtered_df = filtered_df.filter(
            pl.col(selected_gas).is_not_null() & pl.col(selected_gas).is_not_nan()
        ).select(STANDARD_COMPONENTS + [selected_gas])
        filtered_df = add_visual_data_to_gas(filtered_df, selected_gas)
    else:
        filtered_df = filtered_df.select(STANDARD_COMPONENTS)
        filtered_df = add_visual_data_to_aq_index(filtered_df)

    render_colormap(filtered_df)
    st.subheader("Station Data Overview")
    visual_columns_to_exclude = [
        "color_r",
        "color_g",
        "color_b",
        "color_a",
        "radius",
        "latitude",
        "longitude",
    ]
    preview_df = filtered_df.drop(
        [col for col in visual_columns_to_exclude if col in filtered_df]
    )

    st.dataframe(
        preview_df.head().to_pandas(), use_container_width=True, hide_index=True
    )


def render_colormap(data: pl.DataFrame, gas: Optional[str] = None) -> None:

    # Convert to Pandas DataFrame
    df_pandas = pd.DataFrame(data.to_dicts())

    scatterplot_layer = pdk.Layer(
        "ScatterplotLayer",
        df_pandas,
        get_position=["longitude", "latitude"],
        get_fill_color="[color_r, color_g, color_b, color_a]",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
    )

    # Set the viewport location to the Center of Prague
    view_state = pdk.ViewState(
        latitude=50.08,
        longitude=14.43,
        zoom=10,
        pitch=0,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[scatterplot_layer],
            initial_view_state=view_state,
            tooltip={"text": "Station: {station_name}\nAQ Index: {AQ_hourly_index}"},  # type: ignore
        )
    )


def main():
    # Load data
    if "aws" in st.secrets and st.secrets["aws"].get("aws_access_key_id"):
        data = load_data_from_s3()
    else:
        file_path = Path(AppConfig.LOCAL_TARGET_PATH)
        data = load_data_locally(file_path)

    # Create the dashboard
    create_dashboard(data)


if __name__ == "__main__":
    main()
