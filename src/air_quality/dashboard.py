from pathlib import Path
from typing import Optional

import streamlit as st
import polars as pl
import pydeck as pdk
import pandas as pd

STANDARD_COMPONENTS = [
    "station_id",
    "station_name",
    "district",
    "longitude",
    "latitude",
    "updated_at",
    "AQ_hourly_index",
]

@st.cache_resource
def load_data(file_path: Path) -> pl.DataFrame:
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
            "color_r": [46, 242, 255],
            "color_g": [204, 244, 55],
            "color_b": [113, 54, 55],
        }
    )
    default = [255, 55, 55]
    return data.join(color_lookup, on="AQ_hourly_index", how="left").with_columns(
        [
            pl.col("color_r").fill_null(default[0]),
            pl.col("color_g").fill_null(default[1]),
            pl.col("color_b").fill_null(default[2]),
            pl.lit(255).alias("color_a"),
            pl.lit(200).alias("radius")
        ]
    )

def add_visual_data_to_gas(data: pl.DataFrame, gas: str) -> pl.DataFrame:
    MIN_RADIUS = 200
    MAX_RADIUS = 2000
    default = [167, 88, 162, 150] # purple

    gas_col = pl.col(gas)
    val_min = gas_col.min()
    val_max = gas_col.max()
    # Normalize the radius
    radius_expr = pl.when(val_min == val_max).then(MIN_RADIUS).otherwise(
            MIN_RADIUS + ((gas_col - val_min) / (val_max - val_min)) * (MAX_RADIUS - MIN_RADIUS)
        )

    return data.with_columns(
            pl.lit(default[0]).alias("color_r"),
            pl.lit(default[1]).alias("color_g"),
            pl.lit(default[2]).alias("color_b"),
            pl.lit(default[3]).alias("color_a"),
            radius_expr.alias("radius")
    )

def create_dashboard(data: pl.DataFrame):
    """Create a Streamlit dashboard to visualize air quality data."""

    st.title("Air Quality Dashboard")
    st.write("This dashboard visualizes air quality data.")

    DISTRICT_OPTIONS = sorted(data["district"].unique().to_list())

    NONE_OPTION = "Overall Index"
    ALL_GASES = sorted(list(set(data.columns) - set(STANDARD_COMPONENTS)))

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
    st.subheader("Data Preview")
    st.dataframe(filtered_df.head().to_pandas())


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
    file_path = Path("air_quality_latest.parquet")
    data = load_data(file_path)

    # Create the dashboard
    create_dashboard(data)


if __name__ == "__main__":
    main()
