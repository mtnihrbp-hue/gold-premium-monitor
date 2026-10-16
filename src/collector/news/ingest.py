"""News ingestion orchestrator.

Wires the existing RSS collector → event classifier → repository persistence.
Non-blocking: any failure returns a degraded summary without stopping the pipeline.
Parallel fetch + batch dedup for performance.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Set, Union
from datetime import datetime

from collector.news.rss import collect_rss_feed
from intelligence.event_classifier import classify_news_item
from database.repository import save_news_event, get_recent_dedup_keys, hold_news_event
from persistence.spool import held_keys


MAX_CONSECUTIVE_FAILED = 3


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
    # Three failed saves in a row and the rest of the run stores nothing: while Neon was suspended
    # (SP_D_HANDOFF.md sections 34, 35.3) each item spent about a second failing, 2.5 minutes a run.
    consecutive_failed, skipped = 0, 0
    # Once a save finds the database out of reach and the item is held (save_news_event returns 0), the
    # rest of the run is held without asking the database again (SP_D_HANDOFF.md section 37.13).
    database_out, held, not_held = False, 0, 0

    # Batch dedup: one query for all recent keys instead of N+1 exists checks; with the items already
    # held, so an item every run fetches again during an outage is held once
    recent_keys: Set[str] = get_recent_dedup_keys(hours=24) | held_keys("news", "dedup_key")

    # -----------------------------------------------------------------------
    # Phase 1: Parallel I/O-bound fetch
    # -----------------------------------------------------------------------
    def _fetch(url: str) -> tuple[str, Union[list, Exception]]:
        try:
            items = collect_rss_feed(url, timeout=(5, 8))
            return url, items[:max_items]
        except Exception as e:
            return url, e

    fetched: Dict[str, Union[list, Exception]] = {}
    max_workers = min(len(sources), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(_fetch, url): url for url in sources}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                _, items = future.result()
                fetched[url] = items
            except Exception as e:
                fetched[url] = e

    # -----------------------------------------------------------------------
    # Phase 2: Sequential processing (DB writes must be serialized)
    # -----------------------------------------------------------------------
    for url in sources:
        items = fetched.get(url)
        source_result = {
            "status": "PENDING",
            "fetched": 0,
            "new": 0,
            "duplicate": 0,
            "failed": 0,
            "error": None,
        }

        if isinstance(items, Exception):
            source_result["status"] = "ERROR"
            source_result["error"] = str(items)
            results[url] = source_result
            continue

        source_result["fetched"] = len(items)

        for raw_item in items:
            if consecutive_failed >= MAX_CONSECUTIVE_FAILED:
                skipped += 1
                continue
            try:
                classified = classify_news_item(raw_item)
                dedup_key = classified.get("dedup_key") or raw_item.get("dedup_key")

                if dedup_key and dedup_key in recent_keys:
                    source_result["duplicate"] += 1
                    total_duplicate += 1
                    continue

                if database_out:
                    if hold_news_event(classified):
                        held += 1
                        recent_keys.add(dedup_key)
                    else:
                        not_held += 1
                    continue

                event_id = save_news_event(classified)
                if event_id > 0:
                    source_result["new"] += 1
                    total_new += 1
                    consecutive_failed = 0
                    recent_keys.add(dedup_key)  # prevent intra-run duplicates
                elif event_id == 0:
                    held += 1
                    database_out = True
                    recent_keys.add(dedup_key)
                else:
                    source_result["failed"] += 1
                    total_failed += 1
                    consecutive_failed += 1
            except Exception:
                source_result["failed"] += 1
                total_failed += 1
                consecutive_failed += 1

        source_result["status"] = "OK"
        results[url] = source_result

    if skipped:
        print(f"NEWS: {MAX_CONSECUTIVE_FAILED} saves failed in a row; {skipped} items of this run not stored")
    if held or not_held:
        print(f"NEWS: the database is out of reach; {held} new items held for later"
              + (f", {not_held} not held (the spool's news share is full)" if not_held else ""))
    return {
        "status": "OK",
        "sources": results,
        "total_new": total_new,
        "total_duplicate": total_duplicate,
        "total_failed": total_failed,
        "total_skipped": skipped,
        "total_held": held,
        "processed_at": datetime.utcnow().isoformat(),
    }
