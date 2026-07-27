from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class V3Route:
    key: str
    label: str
    title: str
    filename: str
    section: str
    description: str


V3_PAGE_ROUTES: tuple[V3Route, ...] = (
    V3Route(
        key="morning_brief",
        label="Home",
        title="Dashboard Home",
        filename="index.html",
        section="Dashboard Home",
        description="Daily evidence, coverage, and dataset health for Product Team research.",
    ),
    V3Route(
        key="product_explorer",
        label="Product Explorer",
        title="Product Explorer",
        filename="product_explorer.html",
        section="Product Explorer",
        description="Search, filter, inspect, and open source-backed product evidence.",
    ),
    V3Route(
        key="competitor",
        label="Competitor Explorer",
        title="Competitor Explorer",
        filename="competitor.html",
        section="Competitor Explorer",
        description="Seller and competitor concentration review.",
    ),
    V3Route(
        key="market_explorer",
        label="Market Explorer",
        title="Market Explorer",
        filename="market_explorer.html",
        section="Market Explorer",
        description="Market scanning by source, category, and product type.",
    ),
)


V3_ROUTE_ALIASES: dict[str, str] = {
    "competitor_explorer.html": "competitor.html",
}


def route_for_filename(filename: str) -> V3Route:
    target = V3_ROUTE_ALIASES.get(filename, filename)
    for route in V3_PAGE_ROUTES:
        if route.filename == target:
            return route
    raise KeyError(f"Unknown Dashboard V3 route: {filename}")
