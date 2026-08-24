"""News ingestion orchestrator.

Wires the existing RSS collector → event classifier → repository persistence.
Non-blocking: any failure returns a degraded summary without stopping the pipeline.
"""

from typing import Dict, Any
from datetime import datetime

from collector.news.rss import collect_rss_feed
from intelligence.event_classifier import classify_news_item
from database.repository import save_news_event, news_event_exists


def run_news_ingestion(config: Dict[str, Any]) -> Dict[str, Any]:
    """Collect, classify, deduplicate, and persist news events.

    Args:
        config: application config dict; expects config["news"] with
                enabled, sources, max_items_per_source keys.

    Returns:
        summary dict with per-source results and totals.
    """
    news_cfg = config.get("news", {})
    if not news_cfg.get("enabled", False):
        return {"status": "DISABLED", "sources": {}, "total_new": 0}

    sources = news_cfg.get("sources", [])
    if not sources:
        return {"status": "NO_SOURCES", "sources": {}, "total_new": 0}

    max_items = news_cfg.get("max_items_per_source", 20)
    results: Dict[str, Any] = {}
    total_new = 0
    total_duplicate = 0
    total_failed = 0

    for url in sources:
        source_result = {
            "status": "PENDING",
            "fetched": 0,
            "new": 0,
            "duplicate": 0,
            "failed": 0,
            "error": None,
        }
        try:
            items = collect_rss_feed(url, timeout=15)
            items = items[:max_items]
            source_result["fetched"] = len(items)

            for raw_item in items:
                try:
                    classified = classify_news_item(raw_item)
                    dedup_key = classified.get("dedup_key") or raw_item.get("dedup_key")

                    if dedup_key and news_event_exists(dedup_key):
                        source_result["duplicate"] += 1
                        total_duplicate += 1
                        continue

                    event_id = save_news_event(classified)
                    if event_id > 0:
                        source_result["new"] += 1
                        total_new += 1
                    else:
                        source_result["failed"] += 1
                        total_failed += 1
                except Exception:
                    source_result["failed"] += 1
                    total_failed += 1

            source_result["status"] = "OK"
        except Exception as e:
            source_result["status"] = "ERROR"
            source_result["error"] = str(e)

        results[url] = source_result

    return {
        "status": "OK",
        "sources": results,
        "total_new": total_new,
        "total_duplicate": total_duplicate,
        "total_failed": total_failed,
        "processed_at": datetime.now().isoformat(),
    }
