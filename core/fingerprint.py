"""
Fingerprint engine — reads history_log.jsonl and computes a
weighted taste trait vector per content type.

Traits scored 0.0–1.0 using frequency + recency decay.
Recomputed on demand or weekly via scheduler.
"""

import json
import math
import datetime
from pathlib import Path
from collections import defaultdict

HISTORY_LOG = "storage/history_log.jsonl"
TASTE_STORE = "storage/taste_store.json"

# YouTube category IDs → human-readable genre
YT_CATEGORY_MAP = {
    "1": "film_animation",
    "2": "autos_vehicles",
    "10": "music",
    "15": "pets_animals",
    "17": "sports",
    "19": "travel_events",
    "20": "gaming",
    "21": "videoblogging",
    "22": "people_blogs",
    "23": "comedy",
    "24": "entertainment",
    "25": "news_politics",
    "26": "howto_style",
    "27": "education",
    "28": "science_technology",
    "29": "nonprofits_activism",
}

# Tag clusters → trait labels
TRAIT_TAG_CLUSTERS = {
    "documentary": ["documentary", "docuseries", "true story", "real events", "investigation"],
    "science_tech": ["science", "technology", "physics", "space", "engineering", "AI", "machine learning"],
    "history": ["history", "historical", "ancient", "world war", "civilization"],
    "comedy": ["comedy", "funny", "humor", "satire", "stand-up", "parody"],
    "music_ambient": ["ambient", "lofi", "instrumental", "jazz", "classical", "meditation"],
    "storytelling": ["narrative", "story", "film", "cinema", "short film"],
    "education": ["explained", "tutorial", "how to", "course", "learn", "lecture"],
    "sports": ["sports", "football", "soccer", "basketball", "cricket", "highlights"],
    "news_analysis": ["news", "politics", "analysis", "current events", "debate"],
    "travel": ["travel", "explore", "vlog", "adventure", "destination"],
}

# Channel keywords → trait
CHANNEL_TRAIT_MAP = {
    "kurzgesagt": "science_tech",
    "veritasium": "science_tech",
    "vsauce": "science_tech",
    "ted": "education",
    "lex fridman": "education",
    "netflix": "storytelling",
    "a24": "storytelling",
    "pitchfork": "music_ambient",
    "bbc": "news_analysis",
    "cnn": "news_analysis",
}


def load_signals():
    """Load all signals from the JSONL log."""
    signals = []
    path = Path(HISTORY_LOG)
    if not path.exists():
        return signals
    with open(path, "r") as f:
        for line in f:
            try:
                signals.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    return signals


def recency_weight(captured_at_str, half_life_days=60):
    """Exponential decay — recent signals matter more."""
    try:
        captured = datetime.datetime.fromisoformat(captured_at_str)
        age_days = (datetime.datetime.utcnow() - captured).days
        return math.exp(-0.693 * age_days / half_life_days)
    except Exception:
        return 0.5


def tags_to_traits(tags):
    """Map a list of video tags to trait labels."""
    matched = set()
    tags_lower = [t.lower() for t in tags]
    for trait, keywords in TRAIT_TAG_CLUSTERS.items():
        for kw in keywords:
            if any(kw in tag for tag in tags_lower):
                matched.add(trait)
    return list(matched)


def channel_to_trait(channel_name):
    """Map known channel names to traits."""
    lower = channel_name.lower()
    for keyword, trait in CHANNEL_TRAIT_MAP.items():
        if keyword in lower:
            return trait
    return None


def category_to_trait(category_id):
    """Map YouTube category ID to a rough trait."""
    cat = YT_CATEGORY_MAP.get(str(category_id), "")
    trait_map = {
        "music": "music_ambient",
        "science_technology": "science_tech",
        "education": "education",
        "comedy": "comedy",
        "sports": "sports",
        "news_politics": "news_analysis",
        "travel_events": "travel",
        "film_animation": "storytelling",
    }
    return trait_map.get(cat)


def compute_fingerprint(signals):
    """
    Compute a weighted trait score vector from all signals.
    Returns dict of {trait: score_0_to_1}.
    """
    trait_scores = defaultdict(float)
    trait_counts = defaultdict(int)

    for signal in signals:
        base_weight = float(signal.get("signal_weight", 0.5))
        recency = recency_weight(signal.get("captured_at", ""))
        weight = base_weight * recency

        # Event type multiplier
        event = signal.get("event", "")
        if event == "liked":
            weight *= 1.5
        elif event == "subscribed":
            weight *= 1.0
        elif event == "watch_later":
            weight *= 0.8

        # Extract traits from this signal
        traits_found = []

        tags = signal.get("tags", [])
        if tags:
            traits_found.extend(tags_to_traits(tags))

        channel = signal.get("channel", "") or signal.get("channel_title", "")
        ct = channel_to_trait(channel)
        if ct:
            traits_found.append(ct)

        cat_trait = category_to_trait(signal.get("category_id", ""))
        if cat_trait:
            traits_found.append(cat_trait)

        for trait in set(traits_found):
            trait_scores[trait] += weight
            trait_counts[trait] += 1

    if not trait_scores:
        return {}

    # Normalize to 0.0–1.0
    max_score = max(trait_scores.values())
    fingerprint = {
        trait: round(score / max_score, 3)
        for trait, score in trait_scores.items()
    }

    return dict(sorted(fingerprint.items(), key=lambda x: -x[1]))


def load_fingerprint():
    """Load existing fingerprint from disk."""
    path = Path(TASTE_STORE)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_fingerprint(fingerprint):
    """Persist fingerprint to disk."""
    path = Path(TASTE_STORE)
    path.parent.mkdir(exist_ok=True)
    store = {
        "updated_at": datetime.datetime.utcnow().isoformat(),
        "signal_count": len(load_signals()),
        "traits": fingerprint,
    }
    with open(path, "w") as f:
        json.dump(store, f, indent=2)
    return store


def recompute_and_save():
    """Full recompute cycle — call weekly or on demand."""
    signals = load_signals()
    if not signals:
        print("No signals found. Run: python connectors/youtube_connector.py --fetch")
        return None

    print(f"Computing fingerprint from {len(signals)} signals...")
    fingerprint = compute_fingerprint(signals)
    store = save_fingerprint(fingerprint)

    print("\nTaste fingerprint:")
    for trait, score in list(fingerprint.items())[:10]:
        bar = "█" * int(score * 20)
        print(f"  {trait:<20} {bar:<20} {score:.0%}")

    print(f"\nSaved to {TASTE_STORE}")
    return store


if __name__ == "__main__":
    recompute_and_save()
