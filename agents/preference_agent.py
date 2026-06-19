"""
Preference agent — understands natural language commands like:
  "ignore soccer content"
  "more jazz on weekends"
  "no horror after 10pm"
  "reset all preferences"

Stores rules in storage/preferences.json and applies them
as hard filters + soft boosts to every recommendation cycle.
"""

import json
import datetime
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

PREFERENCES_FILE = "storage/preferences.json"

SYSTEM_PROMPT = """You are CuratorTaste AI's preference parser.

The user gives you a natural language command about what content they want to include or exclude.
Parse it into a structured preference rule with these fields:

{
  "action": "ignore" | "boost" | "filter_by_time" | "reset",
  "content_type": "all" | "youtube" | "movies" | "music",
  "topic": "<topic keyword or null>",
  "genre": "<genre keyword or null>",
  "time_condition": "<e.g. after 10pm, weekends, mornings, or null>",
  "reason": "<brief human-readable summary of the rule>",
  "confidence": 0.0-1.0
}

Return ONLY valid JSON, no preamble, no markdown.

Examples:
- "ignore soccer content" → {"action":"ignore","content_type":"all","topic":"soccer","genre":null,"time_condition":null,"reason":"Exclude all soccer content","confidence":0.98}
- "no horror after 10pm" → {"action":"filter_by_time","content_type":"movies","topic":null,"genre":"horror","time_condition":"after 10pm","reason":"Hide horror movies after 10pm","confidence":0.95}
- "more jazz on weekends" → {"action":"boost","content_type":"music","topic":null,"genre":"jazz","time_condition":"weekends","reason":"Boost jazz music on weekend recommendations","confidence":0.97}
- "reset all preferences" → {"action":"reset","content_type":"all","topic":null,"genre":null,"time_condition":null,"reason":"Clear all stored preferences","confidence":0.99}
"""


def load_preferences():
    """Load all stored preference rules."""
    path = Path(PREFERENCES_FILE)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"rules": [], "updated_at": None}


def save_preferences(prefs):
    """Persist preferences to disk."""
    path = Path(PREFERENCES_FILE)
    path.parent.mkdir(exist_ok=True)
    prefs["updated_at"] = datetime.datetime.utcnow().isoformat()
    with open(path, "w") as f:
        json.dump(prefs, f, indent=2)


def parse_preference_command(command: str) -> dict:
    """Use Claude to parse a natural language preference command into a rule."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": command}],
    )
    raw = response.content[0].text.strip()
    return json.loads(raw)


def add_preference(command: str, verbose=True) -> dict:
    """
    Parse a command and add/apply it to the preference store.
    Returns the parsed rule.
    """
    if verbose:
        print(f"Processing: \"{command}\"")

    rule = parse_preference_command(command)

    if rule.get("action") == "reset":
        prefs = {"rules": []}
        save_preferences(prefs)
        if verbose:
            print("All preferences reset.")
        return rule

    prefs = load_preferences()

    # Avoid duplicate rules (same action + topic/genre + time)
    key = (rule.get("action"), rule.get("topic"), rule.get("genre"), rule.get("time_condition"))
    existing_keys = [
        (r.get("action"), r.get("topic"), r.get("genre"), r.get("time_condition"))
        for r in prefs["rules"]
    ]
    if key not in existing_keys:
        rule["added_at"] = datetime.datetime.utcnow().isoformat()
        rule["command_raw"] = command
        prefs["rules"].append(rule)
        save_preferences(prefs)
        if verbose:
            print(f"Rule added: {rule['reason']}")
    else:
        if verbose:
            print(f"Rule already exists: {rule['reason']}")

    return rule


def apply_preferences_to_candidates(candidates: list, context: dict = None) -> list:
    """
    Filter and re-rank a list of content candidates based on stored rules.

    candidates: list of dicts with keys: title, genre, topic, content_type, score
    context: dict with keys: hour (0-23), day_of_week (0=Mon..6=Sun)

    Returns filtered + adjusted candidates list.
    """
    prefs = load_preferences()
    rules = prefs.get("rules", [])
    if not rules:
        return candidates

    hour = (context or {}).get("hour", 12)
    dow = (context or {}).get("day_of_week", 0)
    is_weekend = dow >= 5
    is_after_10pm = hour >= 22
    is_morning = 6 <= hour <= 10

    def matches_time(time_condition):
        if not time_condition:
            return True
        tc = time_condition.lower()
        if "after 10pm" in tc and not is_after_10pm:
            return False
        if "weekend" in tc and not is_weekend:
            return False
        if "morning" in tc and not is_morning:
            return False
        return True

    filtered = []
    for item in candidates:
        item_topic = (item.get("topic") or "").lower()
        item_genre = (item.get("genre") or "").lower()
        item_type = (item.get("content_type") or "all").lower()
        excluded = False
        boost = 1.0

        for rule in rules:
            r_topic = (rule.get("topic") or "").lower()
            r_genre = (rule.get("genre") or "").lower()
            r_type = (rule.get("content_type") or "all").lower()
            r_time = rule.get("time_condition")

            # Type match
            type_match = r_type == "all" or r_type == item_type

            # Content match
            topic_match = r_topic and r_topic in item_topic
            genre_match = r_genre and r_genre in item_genre
            content_match = topic_match or genre_match

            if not type_match or not content_match:
                continue

            if not matches_time(r_time):
                continue

            action = rule.get("action")
            if action == "ignore":
                excluded = True
                break
            elif action == "filter_by_time":
                excluded = True
                break
            elif action == "boost":
                boost *= 1.4

        if not excluded:
            item = dict(item)
            item["score"] = round(item.get("score", 0.5) * boost, 3)
            filtered.append(item)

    return sorted(filtered, key=lambda x: -x.get("score", 0))


def list_preferences(verbose=True) -> list:
    """Return and optionally print all active preference rules."""
    prefs = load_preferences()
    rules = prefs.get("rules", [])
    if verbose:
        if not rules:
            print("No preferences set.")
        else:
            print(f"{len(rules)} active preference rule(s):\n")
            for i, r in enumerate(rules, 1):
                time_note = f" [{r['time_condition']}]" if r.get("time_condition") else ""
                print(f"  {i}. [{r['action'].upper()}] {r['reason']}{time_note}")
    return rules


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        add_preference(cmd)
        print("\nAll active rules:")
        list_preferences()
    else:
        print("Usage: python agents/preference_agent.py ignore soccer content")
        print("       python agents/preference_agent.py no horror after 10pm")
        print("       python agents/preference_agent.py reset all preferences")
