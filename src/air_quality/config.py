import os


class AppConfig:
    # Environment and safety flags
    ENV: str = os.environ.get("ENV", "dev").lower()
    IS_LAMBDA: bool = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    ALLOW_CLOUD_WRITE: bool = IS_LAMBDA or (
        os.environ.get("ALLOW_LOCAL_CLOUD_WRITE", "false").lower() == "true"
    )

    # Infrastructure storage paths
    BUCKET_NAME: str = os.environ.get("DATA_HEALTH_BUCKET_NAME", "")
    S3_TARGET_KEY: str = "extracted/air_quality_latest.parquet"
    LOCAL_TARGET_PATH: str = "air_quality_latest.parquet"

    # API source
    GOLEMIO_BASE_URL: str = "https://api.golemio.cz/v2/"
    GOLEMIO_ENDPOINT: str = "/airqualitystations"
    GOLEMIO_API_TOKEN: str = os.environ.get("GOLEMIO_API_TOKEN", "")

    @classmethod
    def validate(cls) -> None:
        if not cls.GOLEMIO_API_TOKEN:
            raise ValueError(
                "CRITICAL: GOLEMIO_API_TOKEN is missing in environment variables."
            )
        if (cls.ALLOW_CLOUD_WRITE or cls.ENV != "dev") and not cls.BUCKET_NAME:
            raise ValueError(
                "CRITICAL: BUCKET_NAME is missing in environment variables."
            )
