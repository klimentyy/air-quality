import logging
from typing import Any, Dict, Optional
import httpx
from polars.dataframe import DataFrame
from air_quality.utils.golemio_processor import process_air_quality_data
from air_quality.ingestors.base_client import BaseAirQualityClient
from air_quality.config import AppConfig

logger = logging.getLogger(__name__)


class GolemioClient(BaseAirQualityClient):

    def __init__(self, api_token: Optional[str] = None) -> None:
        self.api_token = api_token or AppConfig.GOLEMIO_API_TOKEN
        if not self.api_token:
            raise ValueError("Golemio API Token missing.")

        self.headers = {"X-Access-Token": self.api_token, "Accept": "application/json"}

    def _fetch_raw_json(self, limit: Optional[int] = None) -> Dict[str, Any]:
        url = AppConfig.get_golemio_url()
        params = {"limit": limit} if limit else {}


        timeout = httpx.Timeout(30.0, connect=5.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    def get_cleaned_data(self, limit: Optional[int] = None) -> DataFrame:
        logger.info("Extracting raw JSON from Golemio API...")
        raw_json = self._fetch_raw_json(limit=limit)

        logger.info("Transforming Golemio GeoJSON via Polars pipeline...")
        return process_air_quality_data(raw_json)  # type: ignore
