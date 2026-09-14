"""Rebuild a complete dashboard; image review is a label, not a dataset filter."""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from amazon_market_spy.dashboard_v2.services import DashboardService
from amazon_market_spy.dashboard_v2.generator import generate_dashboard_v2
from amazon_market_spy.dashboard_v2.pages import _product_explorer_products, _pod_filter_bucket, _seller_summaries, _market_group_payload

def rebuild(source, dest):
    source, dest = Path(source).resolve(), Path(dest).resolve()
    if source == dest:
        raise ValueError("Use a separate output directory to preserve raw data")
    dest.mkdir(parents=True, exist_ok=True)
    # Preserve complete coverage and history, including unreviewed products.
    for name in ("latest_products.csv", "historical_comparison.csv", "priority_board.csv",
                 "lark_trend_alerts.csv", "product_trends.csv", "seller_intelligence.csv", "niche_intelligence.csv"):
        if (source/name).exists():
            shutil.copy2(source/name, dest/name)
    data = DashboardService(dest).load()
    products = _product_explorer_products(data)
    counts = {key: sum(_pod_filter_bucket(p)==key for p in products) for key in ("pod","non_pod","unknown")}
    result = generate_dashboard_v2(dest, data=data)
    notice = (f'<div style="padding:12px 24px;background:#fff8e6;color:#433515">'
              f'All scanned products are included in overview pages. '
              f'<a href="product_explorer.html?pod=pod">{counts["pod"]:,} confirmed POD</a> | '
              f'<a href="product_explorer.html?pod=unknown">{counts["unknown"]:,} Needs Image Review</a> | '
              '<a href="product_explorer.html?pod=all">View all products</a></div>')
    for page in result["pages"]:
        path=Path(page["path"])
        html=path.read_text(encoding="utf-8").replace("<body>","<body>"+notice,1)
        path.write_text("\n".join(line.rstrip() for line in html.splitlines())+"\n",encoding="utf-8")
    all_rows = data["product_explorer_products"]
    summary={"products":len(products), "observations":len(all_rows), "image_review":counts,
             "seller_groups":len(_seller_summaries(all_rows)),
             "market_groups": {k:len(v) for k,v in _market_group_payload(all_rows).items()}}
    (dest/"build_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary),flush=True)
    return summary

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    rebuild(args.source,args.output)
