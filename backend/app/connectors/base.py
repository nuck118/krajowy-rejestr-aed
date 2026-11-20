from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.deduplication import RawRecord


@dataclass(slots=True)
class FetchResult:
    fetched_count: int
    rejected_count: int
    records: list[RawRecord]


class BaseConnector(ABC):
    source_name: str

    @abstractmethod
    async def fetch(self) -> FetchResult:
        raise NotImplementedError
