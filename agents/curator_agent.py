"""
CuratorTaste AI — main curator agent.

Reads your taste fingerprint + signal history + active preferences,
then uses Claude to reason over them and generate ranked recommendations
with natural-language explanations.

Usage:
    python agents/curator_agent.py                    # Get recommendations now
    python agents/curator_agent.py --mood chill       # Override mood
    python agents/curator_agent.py --type movies      # Filter content type
    python agents/curator_agent.py --command "ignore soccer content"
"""

import json
import datetime
import click
from pathlib import Path
import anthropic
from dotenv import load_dotenv

from agents.preference_agent import add_preference, apply_preferences_to_candidates, list_preferences
from core.fingerprint import load_fingerprint, recompute_and_save

load_dotenv()

HISTORY_LOG = "storage/history_log.jsonl"
TASTE_STORE = "storage/taste_store.json"

CURATOR_SYSTEM = """You are CuratorTaste AI — a personal entertainment curator with deep knowledge of the user's taste.

You receive:
1. The user's taste fingerprint (trait scores 0-1)
2. Recent watch/listen history signals
3. Current context (time, day, mood)
4. Active preference rules (things to ignore or boost)

Your job: recommend 5 pieces of content (YouTube videos, movies, or music albums/songs) that match this person's fingerprint RIGHT NOW.

Rules:
- Respect all preference rules absolutely (ignore = never recommend, boost = rank higher)
- Match content to the time-of-day context (late night = calm, weekend morning = exploratory)
- Explain WHY each pick matches their fingerprint in one sentence
- Be specific — real titles, real creators, real albums
- Score each pick 0.0-1.0 for fingerprint match

Respond ONLY with valid JSON in this format:
{
  "context_note": "<one sentence about why these picks fit right now>",
  "recommendations": [
    {
      "title": "<exact title>",
      "creator": "<channel / director / artist>",
      "content_type": "youtube|movie|music",
      "genre": "<genre>",
      "topic": "<main topic keyword>",
      "why": "<one sentence — which fingerprint trait this hits>",
      "score": 0.0-1.0
    }
  ]
}
"""


def get_context():
    """Build current time/mood context."""
    now = datetime.datetime.now()
    hour = now.hour
    dow = now.weekday()

    if 6 <= hour <= 9:
        time_slot = "morning"
        mood_default = "focused"
    elif 10 <= hour <= 12:
        time_slot = "late_morning"
        mood_default = "exploratory"
    elif 13 <= hour <= 17:
        time_slot = "afternoon"
        mood_default = "active"
    elif 18 <= hour <= 21:
        time_slot = "evening"
        mood_default = "relaxed"
    else:
        time_slot = "late_night"
        mood_default = "chill"

    return {
        "hour": hour,
        "day_of_week": dow,
        "day_name": now.strftime("%A"),
        "time_slot": time_slot,
        "mood_default": mood_default,
        "is_weekend": dow >= 5,
        "timestamp": now.isoformat(),
    }


def load_recent_signals(n=20):
    """Load the N most recent signals from the history log."""
    path = Path(HISTORY_LOG)
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    signals = []
    for line in reversed(lines[-n * 2:]):
        try:
            signals.append(json.loads(line))
        except Exception:
            pass
    return signals[:n]


def build_curator_prompt(fingerprint, signals, context, mood_override=None, content_type_filter=None):
    """Construct the user message for the curator agent."""
    mood = mood_override or context["mood_default"]

    fp_top = sorted(fingerprint.get("traits", {}).items(), key=lambda x: -x[1])[:8]
    fp_str = "\n".join([f"  {trait}: {score:.0%}" for trait, score in fp_top])

    recent_titles = [s.get("title", s.get("channel_title", "")) for s in signals[:10] if s.get("title") or s.get("channel_title")]
    recent_str = "\n".join([f"  - {t}" for t in recent_titles]) if recent_titles else "  (no history yet)"

    type_note = f"\nContent type filter: {content_type_filter}" if content_type_filter else ""

    return f"""Taste fingerprint (top traits):
{fp_str}

Recent watch/listen history:
{recent_str}

Current context:
  Time: {context['hour']}:00 ({context['time_slot']})
  Day: {context['day_name']} ({'weekend' if context['is_weekend'] else 'weekday'})
  Mood: {mood}
{type_note}

Please recommend 5 pieces of content perfectly matched to this fingerprint and context."""


def get_recommendations(mood=None, content_type=None, verbose=True):
    """Run the full curator agent and return recommendations."""
    fingerprint = load_fingerprint()
    if not fingerprint or not fingerprint.get("traits"):
        print("No fingerprint found. Recomputing from signals...")
        fingerprint = recompute_and_save() or {}

    signals = load_recent_signals()
    context = get_context()

    if verbose:
        print(f"\nCuratorTaste AI — {context['day_name']} {context['hour']}:00 ({context['time_slot']})")
        print(f"Mood: {mood or context['mood_default']} | Signals: {len(signals)}\n")

    prompt = build_curator_prompt(fingerprint, signals, context, mood, content_type)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=CURATOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    result = json.loads(raw)

    # Apply preference filters
    candidates = result.get("recommendations", [])
    filtered = apply_preferences_to_candidates(candidates, context)
    result["recommendations"] = filtered

    if verbose:
        print(f"Context: {result.get('context_note', '')}\n")
        for i, rec in enumerate(result["recommendations"], 1):
            icon = {"youtube": "▶", "movie": "🎬", "music": "♪"}.get(rec["content_type"], "•")
            print(f"{i}. {icon} {rec['title']} — {rec['creator']}")
            print(f"   {rec['why']}")
            print(f"   Match: {rec['score']:.0%} | {rec['genre']}\n")

    return result


@click.command()
@click.option("--mood", default=None, help="Override mood: chill, focused, exploratory, active")
@click.option("--type", "content_type", default=None, help="Filter: youtube, movies, music")
@click.option("--command", default=None, help="Add a preference command: 'ignore soccer content'")
@click.option("--list-prefs", is_flag=True, help="Show all active preference rules")
@click.option("--recompute", is_flag=True, help="Force recompute fingerprint from signals")
def main(mood, content_type, command, list_prefs, recompute):
    """CuratorTaste AI — your personal entertainment agent."""
    if command:
        add_preference(command)
        print()

    if list_prefs:
        list_preferences()
        return

    if recompute:
        recompute_and_save()
        print()

    get_recommendations(mood=mood, content_type=content_type)


if __name__ == "__main__":
    main()
