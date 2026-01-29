from abc import ABC, abstractmethod
from typing import List


class ImageSource(ABC):
    name: str

    @abstractmethod
    def fetch_urls(self, keyword: str, limit: int) -> List[str]:
        raise NotImplementedError
