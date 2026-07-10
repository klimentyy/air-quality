import logging
from air_quality.config import AppConfig
from air_quality.writers.writer import DataWriter, S3Writer

from air_quality.ingestors.base_client import BaseAirQualityClient
from air_quality.ingestors.golemio_client import GolemioClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_pipeline(
    client: BaseAirQualityClient, writer: DataWriter, target: str = "air_quality_latest.parquet"
) -> None:
    """Runs ETL cycle utilizing the passed extraction strategy"""
    try:
        flat_df = client.get_cleaned_data()

        if flat_df.height > 0:
            writer.write(flat_df, target)
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
    
    AppConfig.validate()

    current_strategy = GolemioClient()
    if AppConfig.IS_LAMBDA or AppConfig.ALLOW_CLOUD_WRITE:
        writer = S3Writer()
        target = AppConfig.S3_TARGET_KEY
    else:
        from air_quality.writers.writer import LocalFileWriter

        writer = LocalFileWriter()
        target = AppConfig.LOCAL_TARGET_PATH
        
    run_pipeline(client=current_strategy, writer=writer, target=target)


if __name__ == "__main__":
    main()
