from __future__ import annotations

from pathlib import Path
from typing import Any

from ...dashboard_v2.services import DashboardDataError, DashboardService as DashboardV2Service


class DashboardService:
    """Read existing presentation artifacts for Dashboard V3 pages."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self._v2_service = DashboardV2Service(self.output_dir)

    @classmethod
    def for_v3_output(cls, output_dir: Path) -> "DashboardService":
        output_dir = Path(output_dir)
        source_dir = output_dir.parent if output_dir.name.lower() == "v3" else output_dir
        return cls(source_dir)

    def load(self) -> dict[str, Any]:
        return self._v2_service.load()

    def validate(self, data: dict[str, Any]) -> None:
        self._v2_service.validate(data)
