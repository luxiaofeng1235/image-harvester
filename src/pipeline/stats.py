from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class RunStats:
    total_urls: int = 0
    saved: int = 0
    filtered: int = 0
    duplicates: int = 0
    blocked: int = 0
    errors: int = 0
    failure_reasons: Dict[str, int] = field(default_factory=dict)

    def add_reason(self, reason: str) -> None:
        if not reason:
            return
        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1

    def as_dict(self) -> Dict:
        top = sorted(self.failure_reasons.items(), key=lambda x: x[1], reverse=True)
        return {
            "total_urls": self.total_urls,
            "saved": self.saved,
            "filtered": self.filtered,
            "duplicates": self.duplicates,
            "blocked": self.blocked,
            "errors": self.errors,
            "failure_reasons": top,
        }
