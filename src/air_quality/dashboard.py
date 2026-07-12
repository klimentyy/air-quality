from pathlib import Path
from typing import Callable

import streamlit as st
import polars as pl

STANDARD_COMPONENTS = ["station_id", "station_name", "district", "longitude", "latitude", "updated_at"]

@st.cache_data
def load_data(file_path: Path) -> pl.DataFrame:
    """Load data from a Parquet file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.suffix == ".parquet":
        raise ValueError("File must be a Parquet file.")

    return pl.read_parquet(file_path)

def create_dashboard(data: pl.DataFrame):
    """Create a Streamlit dashboard to visualize air quality data."""

    st.title("Air Quality Dashboard")
    st.write("This dashboard visualizes air quality data.")

    with st.sidebar:
        st.header("Filters")
        unique_gases = set(data.columns) - set(STANDARD_COMPONENTS)
        selected_gas = st.selectbox("Select Gas Type", options=unique_gases) 
        data = data.filter(pl.col(selected_gas).is_not_null()).select(STANDARD_COMPONENTS + [selected_gas])
        

    st.write(f"Selected Gas Type: {selected_gas}")

    map_data = data.select(["latitude", "longitude"]).drop_nulls()
    st.map(map_data.to_pandas(), zoom=10, use_container_width=True)

    # Display the data
    st.subheader("Data Preview")
    st.dataframe(data.head())


def main():
    # Load data
    file_path = Path("air_quality_latest.parquet")
    data = load_data(file_path)

    # Create the dashboard
    create_dashboard(data)

if __name__ == "__main__":
    main()