import os
from urllib.parse import urljoin

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AppConfigMeta(type):
    @property
    def ENV(cls) -> str:
        return os.environ.get("ENV", "dev").lower()

    @ENV.setter
    def ENV(cls, value: str) -> None:
        os.environ["ENV"] = value

    @property
    def IS_LAMBDA(cls) -> bool:
        return os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None

    @IS_LAMBDA.setter
    def IS_LAMBDA(cls, value: bool) -> None:
        if value:
            os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "true"
        else:
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

    @property
    def ALLOW_CLOUD_WRITE(cls) -> bool:
        return cls.IS_LAMBDA or (
            os.environ.get("ALLOW_LOCAL_CLOUD_WRITE", "false").lower() == "true"
        )

    @ALLOW_CLOUD_WRITE.setter
    def ALLOW_CLOUD_WRITE(cls, value: bool) -> None:
        os.environ["ALLOW_LOCAL_CLOUD_WRITE"] = str(value).lower()

    @property
    def BUCKET_NAME(cls) -> str:
        return os.environ.get("DATA_HEALTH_BUCKET_NAME", "")

    @BUCKET_NAME.setter
    def BUCKET_NAME(cls, value: str) -> None:
        os.environ["DATA_HEALTH_BUCKET_NAME"] = value

    @property
    def GOLEMIO_API_TOKEN(cls) -> str:
        return os.environ.get("GOLEMIO_API_TOKEN", "")

    @GOLEMIO_API_TOKEN.setter
    def GOLEMIO_API_TOKEN(cls, value: str) -> None:
        os.environ["GOLEMIO_API_TOKEN"] = value


class AppConfig(metaclass=AppConfigMeta):
    # Infrastructure storage paths
    S3_TARGET_KEY: str = "extracted/air_quality_latest.parquet"
    LOCAL_TARGET_PATH: str = "air_quality_latest.parquet"

    # API source
    GOLEMIO_BASE_URL: str = "https://api.golemio.cz/v2/"
    GOLEMIO_ENDPOINT: str = "airqualitystations"

    @classmethod
    def get_golemio_url(cls) -> str:
        return urljoin(cls.GOLEMIO_BASE_URL, cls.GOLEMIO_ENDPOINT)

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

