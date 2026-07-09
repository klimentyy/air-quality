
from abc import ABC, abstractmethod
from typing import Optional
from polars.dataframe import DataFrame



class BaseAirQualityClient(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def get_cleaned_data(self, limit: Optional[int] = None) -> DataFrame:
           pass

