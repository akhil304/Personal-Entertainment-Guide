"""
Mood engine — learns your personal time-of-day content patterns
from history and maps them to mood contexts for smarter picks.
"""

import json
import datetime
from collections import defaultdict
from pathlib import Path

HISTORY_LOG = "storage/history_log.jsonl"
MOOD_PROFILE = "storage/mood_profile.json"


def load_signals_with_time():
    """Load signals that have a captured_at timestamp."""
    signals = []
    path = Path(HISTORY_LOG)
    if not path.exists():
        return signals
    with open(path) as f:
        for line in f:
            try:
                s = json.loads(line)
                if s.get("captured_at"):
                    signals.append(s)
            except Exception:
                pass
    return signals


def build_time_patterns(signals):
    """
    Analyse what content types / traits appear at which hours + days.
    Returns a nested dict: {hour_slot: {content_trait: count}}
    """
    patterns = defaultdict(lambda: defaultdict(int))

    for s in signals:
        try:
            dt = datetime.datetime.fromisoformat(s["captured_at"])
            hour = dt.hour
            dow = dt.weekday()

            slot = f"{'weekend' if dow >= 5 else 'weekday'}_{_hour_slot(hour)}"

            # Count content signals per slot
            for tag in s.get("tags", [])[:5]:
                patterns[slot][tag.lower()] += 1

            category = s.get("category_id", "")
            if category:
                patterns[slot][f"cat_{category}"] += 1

        except Exception:
            pass

    return {slot: dict(traits) for slot, traits in patterns.items()}


def _hour_slot(hour):
    if 5 <= hour < 9:
        return "morning"
    elif 9 <= hour < 13:
        return "midday"
    elif 13 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "late_night"


def resolve_mood(hour=None, day_of_week=None, patterns=None):
    """
    Given current time and learned patterns, return a mood context dict.
    Falls back to rule-based defaults if no patterns exist.
    """
    if hour is None:
        now = datetime.datetime.now()
        hour = now.hour
        day_of_week = now.weekday()

    is_weekend = day_of_week >= 5
    slot_key = f"{'weekend' if is_weekend else 'weekday'}_{_hour_slot(hour)}"
    slot_label = _hour_slot(hour)

    # Default mood rules
    defaults = {
        "morning":    {"mood": "focused",     "energy": "medium", "length_pref": "short"},
        "midday":     {"mood": "exploratory",  "energy": "high",   "length_pref": "medium"},
        "afternoon":  {"mood": "active",       "energy": "high",   "length_pref": "medium"},
        "evening":    {"mood": "relaxed",      "energy": "low",    "length_pref": "long"},
        "late_night": {"mood": "chill",        "energy": "very_low","length_pref": "long"},
    }

    ctx = defaults.get(slot_label, {"mood": "relaxed", "energy": "medium", "length_pref": "medium"})
    ctx["slot"] = slot_key
    ctx["hour"] = hour
    ctx["is_weekend"] = is_weekend

    # Enrich with top patterns if available
    if patterns and slot_key in patterns:
        top = sorted(patterns[slot_key].items(), key=lambda x: -x[1])[:3]
        ctx["learned_top_traits"] = [t for t, _ in top]

    return ctx


def recompute_mood_profile():
    """Full recompute of time patterns from signal log."""
    signals = load_signals_with_time()
    if not signals:
        print("No timestamped signals yet. Run: python connectors/youtube_connector.py --fetch")
        return {}

    patterns = build_time_patterns(signals)

    profile = {
        "updated_at": datetime.datetime.utcnow().isoformat(),
        "signal_count": len(signals),
        "patterns": patterns,
    }

    path = Path(MOOD_PROFILE)
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"Mood profile saved — {len(patterns)} time slots learned from {len(signals)} signals.")
    return profile


def load_mood_profile():
    path = Path(MOOD_PROFILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    recompute_mood_profile()
    profile = load_mood_profile()
    now = datetime.datetime.now()
    ctx = resolve_mood(now.hour, now.weekday(), profile.get("patterns", {}))
    print(f"\nCurrent mood context:")
    for k, v in ctx.items():
        print(f"  {k}: {v}")
