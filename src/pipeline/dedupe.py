from dataclasses import dataclass, field
from typing import Set


@dataclass
class DedupeIndex:
    url_seen: Set[str] = field(default_factory=set)
    hash_seen: Set[str] = field(default_factory=set)

    def check_url(self, url: str) -> bool:
        return url in self.url_seen

    def add_url(self, url: str) -> None:
        self.url_seen.add(url)

    def check_hash(self, h: str) -> bool:
        return h in self.hash_seen

    def add_hash(self, h: str) -> None:
        self.hash_seen.add(h)
