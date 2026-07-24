from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    source_name: str
    source_type: str
    category: str
    url: str
    priority: int
    active: bool
    row_number: int
    seller_name: str = ""
    seller_url: str = ""
    seller_id: str = ""

    @property
    def display_name(self) -> str:
        return self.seller_name or self.source_name or self.seller_id


@dataclass(frozen=True)
class ScanResult:
    products: list[dict[str, str]]
    errors: list[dict[str, str]]
    output_paths: dict[str, str]
