import logging

from air_quality.ingestors.base_client import BaseAirQualityClient
from air_quality.ingestors.golemio_client import GolemioClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_pipeline(
    client: BaseAirQualityClient, output_path: str = "air_quality_latest.parquet"
) -> None:
    """Runs ETL cycle utilizing the passed extraction strategy"""
    try:
        flat_df = client.get_cleaned_data()

        if not flat_df.is_empty:
            flat_df.write_parquet(output_path)
            logger.info(f"Data successfully stored to {output_path}")
        else:
            logger.warning("Generated DataFrame is empty")
    except Exception as e:
        logger.critical(f"Pipeline broke down: {e}")
        raise


def main(event=None, context=None):
    # Load dotenv for local development only
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    current_strategy = GolemioClient()
    run_pipeline(client=current_strategy)


if __name__ == "__main__":
    main()
