"""
Signal collector — append-only event logger.
Call this whenever you want to manually log a signal
(e.g. "I just watched X and loved it").
"""

import json
import datetime
from pathlib import Path

HISTORY_LOG = "storage/history_log.jsonl"


def log_signal(
    event: str,
    title: str,
    source: str = "manual",
    content_type: str = "youtube",
    genre: str = None,
    topic: str = None,
    creator: str = None,
    signal_weight: float = 1.0,
    extra: dict = None,
):
    """
    Append a single signal to the history log.

    event: 'liked', 'watched', 'skipped', 'saved', 'disliked'
    signal_weight: 1.0 = strong positive, 0.5 = neutral, -0.5 = negative (skipped/disliked)
    """
    entry = {
        "source": source,
        "event": event,
        "content_type": content_type,
        "title": title,
        "creator": creator,
        "genre": genre,
        "topic": topic,
        "signal_weight": signal_weight,
        "captured_at": datetime.datetime.utcnow().isoformat(),
    }
    if extra:
        entry.update(extra)

    path = Path(HISTORY_LOG)
    path.parent.mkdir(exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def log_liked(title, content_type="youtube", **kwargs):
    return log_signal("liked", title, content_type=content_type, signal_weight=1.0, **kwargs)

def log_watched(title, content_type="youtube", **kwargs):
    return log_signal("watched", title, content_type=content_type, signal_weight=0.7, **kwargs)

def log_skipped(title, content_type="youtube", **kwargs):
    return log_signal("skipped", title, content_type=content_type, signal_weight=-0.5, **kwargs)

def log_disliked(title, content_type="youtube", **kwargs):
    return log_signal("disliked", title, content_type=content_type, signal_weight=-1.0, **kwargs)

def log_saved(title, content_type="movies", **kwargs):
    return log_signal("saved", title, content_type=content_type, signal_weight=0.8, **kwargs)


def count_signals():
    path = Path(HISTORY_LOG)
    if not path.exists():
        return 0
    return sum(1 for _ in open(path))


if __name__ == "__main__":
    # Quick test
    log_liked("Kurzgesagt — The Last Human", content_type="youtube", topic="science", creator="Kurzgesagt")
    log_watched("Aftersun (2022)", content_type="movie", genre="drama", creator="Charlotte Wells")
    log_saved("Khruangbin — A La Sala", content_type="music", genre="psychedelic soul", creator="Khruangbin")
    log_skipped("Premier League Highlights", content_type="youtube", topic="soccer")
    print(f"Total signals logged: {count_signals()}")
