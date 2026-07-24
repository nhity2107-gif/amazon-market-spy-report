from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import ensure_parent
from .pages import (
    clean_product_explorer_detail_assets,
    render_data_error_page,
    render_competitor,
    render_idea_explorer,
    render_market_explorer,
    render_morning_brief,
    render_product_explorer,
    write_product_explorer_detail_assets,
)
from .services import DashboardDataError, DashboardService


V2_PAGE_ROUTES = [
    ("Home", "index.html", render_morning_brief),
    ("Idea Explorer", "idea_explorer.html", render_idea_explorer),
    ("Product Explorer", "product_explorer.html", render_product_explorer),
    ("Competitor Explorer", "competitor.html", render_competitor),
    ("Market Explorer", "market_explorer.html", render_market_explorer),
]


def generate_dashboard_v2(output_dir: Path, data: dict[str, Any] | None = None) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    service = DashboardService.for_v2_output(output_dir)
    data_error: DashboardDataError | None = None
    if data is None:
        try:
            presentation_data = service.load()
        except DashboardDataError as exc:
            data_error = exc
            presentation_data = None
    else:
        service.validate(data)
        presentation_data = data

    clean_product_explorer_detail_assets(output_dir)
    assets: list[dict[str, object]] = []
    if data_error is None and presentation_data is not None:
        assets = write_product_explorer_detail_assets(output_dir, presentation_data)

    pages: list[dict[str, str]] = []
    for label, filename, renderer in V2_PAGE_ROUTES:
        path = output_dir / filename
        ensure_parent(path)
        if data_error is not None:
            html = render_data_error_page(label, _active_key_for_filename(filename), str(data_error))
        else:
            html = renderer(presentation_data)
        path.write_text(html, encoding="utf-8")
        pages.append({"label": label, "filename": filename, "path": str(path)})

    return {
        "output_dir": str(output_dir),
        "main_page": str(output_dir / "index.html"),
        "pages": pages,
        "assets": assets,
    }


def _active_key_for_filename(filename: str) -> str:
    return {
        "index.html": "morning_brief",
        "idea_explorer.html": "idea_explorer",
        "product_explorer.html": "product_explorer",
        "competitor.html": "competitor",
        "market_explorer.html": "market_explorer",
    }[filename]
