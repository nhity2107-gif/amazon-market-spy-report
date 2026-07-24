from __future__ import annotations

from .generator import V2_PAGE_ROUTES, generate_dashboard_v2
from .mock_data import MOCK_PRESENTATION_DATA, validate_mock_data_contract

__all__ = [
    "MOCK_PRESENTATION_DATA",
    "V2_PAGE_ROUTES",
    "generate_dashboard_v2",
    "validate_mock_data_contract",
]
