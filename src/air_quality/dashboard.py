import io
import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import boto3
import streamlit as st
import polars as pl
import pydeck as pdk
import pandas as pd

# FIX FATAL PYTHON ERROR (SEGMENTATION FAULT) ON PYTHON 3.13
pd.options.future.infer_string = False
pd.options.mode.string_storage = "python"

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Ensure the src path is in python path to allow absolute imports
src_path = str(Path(__file__).resolve().parents[1])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from air_quality.config import AppConfig  # noqa: E402

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
    "green": [46, 204, 113, 200],  # Very Good
    "yellow": [241, 196, 15, 200],  # Moderate
    "red": [231, 76, 60, 200],  # Poor / Default
    "grey": [149, 165, 166, 150],  # Unknown
    "violet": [155, 89, 182, 160],  # Gas Metric Visuals
}


@st.cache_resource
def get_s3_client() -> "S3Client":
    """Initialize and cache the boto3 S3 client using Streamlit secrets."""
    return boto3.client(
        "s3",
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
        region_name=st.secrets["aws"].get("aws_region"),
    )


@st.cache_data
def load_data_from_s3(
    bucket_name: Optional[str] = None, file_key: str = AppConfig.S3_TARGET_KEY
) -> pl.DataFrame:
    """Download and parse Parquet data from an AWS S3 bucket."""
    # Prioritize st.secrets, fallback to AppConfig
    resolved_bucket = (
        bucket_name
        or st.secrets.get("DATA_HEALTH_BUCKET_NAME")
        or AppConfig.BUCKET_NAME
    )
    if not resolved_bucket:
        raise ValueError("S3 Bucket name must be configured in environment or secrets.")

    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=resolved_bucket, Key=file_key)
        file_bytes = response["Body"].read()
        return pl.read_parquet(io.BytesIO(file_bytes))
    except Exception as e:
        st.error(f"S3 Data fetch failed for bucket '{resolved_bucket}': {e}")
        raise e


@st.cache_data
def load_data_locally(file_path: Path) -> pl.DataFrame:
    """Load Parquet data from the local filesystem."""
    if not file_path.exists():
        raise FileNotFoundError(f"Local database file not found: {file_path}")
    if file_path.suffix != ".parquet":
        raise ValueError("Target file must be in Parquet format.")

    return pl.read_parquet(file_path)


def add_visual_data_to_aq_index(data: pl.DataFrame) -> pl.DataFrame:
    """Add color and radius dimensions to the dataset based on the AQ Hourly Index."""
    # Mapping table for Air Quality values to RGB values
    aq_colors = {
        "1A": RGBA_COLORS["green"][:3],  # Very Good
        "2A": RGBA_COLORS["yellow"][:3],  # Moderate
        "0": RGBA_COLORS["grey"][:3],  # Unknown
    }
    default_color = RGBA_COLORS["red"][:3]

    # Map AQ Index to colors natively using replace_strict()
    return data.with_columns(
        [
            pl.col("AQ_hourly_index")
            .replace_strict(
                {k: v[0] for k, v in aq_colors.items()}, default=default_color[0]
            )
            .alias("color_r"),
            pl.col("AQ_hourly_index")
            .replace_strict(
                {k: v[1] for k, v in aq_colors.items()}, default=default_color[1]
            )
            .alias("color_g"),
            pl.col("AQ_hourly_index")
            .replace_strict(
                {k: v[2] for k, v in aq_colors.items()}, default=default_color[2]
            )
            .alias("color_b"),
            pl.lit(255).alias("color_a"),
            pl.lit(200).alias("radius"),
        ]
    )


def add_visual_data_to_gas(data: pl.DataFrame, gas: str) -> pl.DataFrame:
    """Add color and radius dimensions based on raw concentration values of a target gas."""
    MIN_RADIUS = 200
    MAX_RADIUS = 2000
    default_color = RGBA_COLORS["violet"]

    gas_col = pl.col(gas)
    val_min = gas_col.min()
    val_max = gas_col.max()

    # Dynamic scaling: default to MIN_RADIUS if min and max concentrations are equal
    radius_expr = (
        pl.when(val_min == val_max)
        .then(MIN_RADIUS)
        .otherwise(
            MIN_RADIUS
            + ((gas_col - val_min) / (val_max - val_min)) * (MAX_RADIUS - MIN_RADIUS)
        )
    )

    return data.with_columns(
        pl.lit(default_color[0]).alias("color_r"),
        pl.lit(default_color[1]).alias("color_g"),
        pl.lit(default_color[2]).alias("color_b"),
        pl.lit(default_color[3]).alias("color_a"),
        radius_expr.alias("radius"),
    )


def get_aq_status(index: str) -> str:
    """Resolve an Air Quality Index code to a human-readable status with emojis."""
    status_map = {
        "1A": "🟢 Very Good",
        "2A": "🟡 Moderate",
        "0": "⚪ Unknown",
    }
    return status_map.get(index, "🔴 Poor")


def render_colormap(data: pl.DataFrame) -> None:
    """Render a geospatial pydeck map representing the station data."""
    # Convert Polars DataFrame to a standard Pandas DataFrame (using safe NumPy object backend)
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

    # Viewport initially centered around Prague
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


def create_dashboard(data: pl.DataFrame) -> None:
    """Construct the Streamlit dashboard layout, filters, metrics, and visualization."""
    st.set_page_config(
        page_title="Prague Air Quality Dashboard",
        page_icon="🌍",
        layout="wide",
    )

    st.title("🌍 Prague Air Quality Dashboard")
    st.markdown(
        "Real-time air quality metrics and station observations across Prague districts."
    )

    # Extract filter parameters
    districts = sorted(data["district"].unique().to_list())
    all_gases = sorted(list(set(data.columns) - set(STANDARD_COMPONENTS)))
    OVERALL_INDEX_LABEL = "Overall Air Quality Index"

    # Sidebar Filter Controls
    with st.sidebar:
        st.header("🔍 Filters")
        selected_districts = st.multiselect(
            label="Select Districts", options=districts, default=[]
        )
        selected_gas = st.selectbox(
            label="Select Metric/Gas Type", options=[OVERALL_INDEX_LABEL] + all_gases
        )

    # Filter base dataset
    filtered_df = data
    if selected_districts:
        filtered_df = filtered_df.filter(pl.col("district").is_in(selected_districts))

    # Resolve dominant air quality status (mode of the index)
    aq_modes = filtered_df["AQ_hourly_index"].mode()
    aq_overall = aq_modes[0] if not aq_modes.is_empty() else "0"

    # Data enrichment for visualization
    if selected_gas != OVERALL_INDEX_LABEL:
        # Filter rows that have measurements for the selected gas
        filtered_df = filtered_df.filter(
            pl.col(selected_gas).is_not_null() & pl.col(selected_gas).is_not_nan()
        ).select(STANDARD_COMPONENTS + [selected_gas])

        # Compute median concentration
        median_val = filtered_df[selected_gas].median()
        gas_median = f"{median_val:.2f}" if median_val is not None else "N/A"

        filtered_df = add_visual_data_to_gas(filtered_df, selected_gas)
    else:
        filtered_df = filtered_df.select(STANDARD_COMPONENTS)
        filtered_df = add_visual_data_to_aq_index(filtered_df)

    # Layout: Top KPIs
    st.write("")
    col_left, col_right = st.columns(2)
    with col_left:
        st.metric(
            label="Dominant Air Quality Index",
            value=get_aq_status(aq_overall),
            help=f"Most frequent air quality class in selection: {aq_overall}",
        )
    with col_right:
        if selected_gas != OVERALL_INDEX_LABEL:
            st.metric(
                label=f"Median {selected_gas} Concentration",
                value=gas_median,
                help=f"Median concentration value of {selected_gas} in selected districts.",
            )
    st.write("")

    # Map Visualization
    render_colormap(filtered_df)

    # Station Details Table
    st.subheader("📊 Station Details")
    exclude_cols = {
        "color_r",
        "color_g",
        "color_b",
        "color_a",
        "radius",
        "latitude",
        "longitude",
    }
    preview_df = filtered_df.drop([col for col in exclude_cols if col in filtered_df])

    # Safe Pandas conversion with NumPy backend to display data securely
    st.dataframe(
        pd.DataFrame(preview_df.head().to_dicts()), width="stretch", hide_index=True
    )


def main() -> None:
    """Bootstrap the dashboard by parsing configurations and loading data sources."""
    has_aws_secrets = False
    try:
        if "aws" in st.secrets and st.secrets["aws"].get("aws_access_key_id"):
            has_aws_secrets = True
    except Exception:
        pass

    if has_aws_secrets:
        # Load from AWS S3 Data Lake
        data = load_data_from_s3()
    else:
        # Load from Local Parquet Database
        file_path = Path(AppConfig.LOCAL_TARGET_PATH)
        data = load_data_locally(file_path)

    create_dashboard(data)


if __name__ == "__main__":
    main()
