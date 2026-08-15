"""Manual news input via Telegram fallback.

Normalizes manually supplied news into the same schema as RSS.
Used for testing and fallback when RSS is unavailable.
"""

from datetime import datetime, timezone
import hashlib
from typing import Dict, Any


def normalize_manual_news(
    title: str,
    summary: str = "",
    url: str = "",
    source: str = "telegram",
    published_at=None,
) -> Dict[str, Any]:
    """Normalize a manually supplied news item into the canonical schema.

    Args:
        title: required headline
        summary: optional body text
        url: optional link
        source: origin label (default "telegram")
        published_at: optional datetime; defaults to now

    Returns:
        Normalized news item dict matching RSS output schema
    """
    if not title or not title.strip():
        raise ValueError("title is required")

    title = title.strip()
    summary = summary.strip()
    url = url.strip()

    if published_at is None:
        published_at = datetime.now(timezone.utc)

    collected_at = datetime.now(timezone.utc)

    dedup_key = hashlib.sha256(
        f"{source}:{title.lower()}".encode("utf-8")
    ).hexdigest()[:32]

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "source": source,
        "published_at": published_at,
        "collected_at": collected_at,
        "dedup_key": dedup_key,
    }
