# CuratorTaste AI

> Silently learns your habits. Builds a personal taste fingerprint. Surfaces hidden gems before you know you want them.

## What it does

- Connects to your YouTube, Spotify, and movie accounts
- Builds a personal "taste fingerprint" from your real watch/listen history
- Learns your time-of-day and mood patterns silently
- Accepts natural language commands: *"ignore soccer content"*, *"more jazz on weekends"*
- Surfaces smart recommendations with explanations you can trust

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/akhil304/Personal-Entertainment-Guide.git
cd curatortaste-ai
pip install -r requirements.txt

# 2. Copy env and fill in your keys
cp .env.example .env

# 3. Authenticate with YouTube (opens browser)
python connectors/youtube_connector.py --auth

# 4. Run the curator agent
python agents/curator_agent.py

# 5. Launch the dashboard
open ui/dashboard.html
```

## Architecture

```
Signal capture → Fingerprint engine → Curator agent → Recommendations
     ↑                                      ↑
  YouTube / Spotify / TMDB          Preference commands
                                  ("ignore soccer content")
```

## Setting up API keys

### YouTube Data API v3
1. Go to https://console.cloud.google.com
2. Create a new project → Enable "YouTube Data API v3"
3. Create OAuth 2.0 credentials → Download `client_secret.json`
4. Place `client_secret.json` in the project root
5. Set `YOUTUBE_CLIENT_SECRET_FILE=client_secret.json` in `.env`

### Spotify
1. Go to https://developer.spotify.com/dashboard
2. Create an app → Copy Client ID and Secret
3. Set redirect URI to `http://localhost:8888/callback`

### TMDB (free)
1. Go to https://www.themoviedb.org/settings/api
2. Request an API key (instant approval)

### Anthropic
1. Go to https://console.anthropic.com
2. Create an API key

## Preference commands

The agent understands natural language. Run:

```bash
python agents/curator_agent.py --command "ignore soccer content"
python agents/curator_agent.py --command "more documentary films on weekends"
python agents/curator_agent.py --command "no horror after 10pm"
python agents/curator_agent.py --command "reset all preferences"
```

Preferences are stored in `storage/preferences.json` and applied to every recommendation cycle.

## Week-by-week build plan

| Week | Focus |
|------|-------|
| 1 | Project setup, YouTube OAuth, pull liked videos |
| 2 | Watch history signal capture, JSONL logging |
| 3 | Fingerprint engine v1 — trait scoring |
| 4 | Fingerprint persistence + weekly recompute |
| 5 | Curator agent — LLM reasoning loop |
| 6 | Preference command system (ignore/boost/filter) |
| 7 | Mood + time-of-day layer |
| 8 | Dashboard UI + end-to-end test |

## File structure

```
curatortaste-ai/
├── core/
│   ├── fingerprint.py        # Taste DNA builder
│   ├── signal_collector.py   # Event logger
│   ├── mood_engine.py        # Time → mood context
│   └── recommender.py        # Scoring + ranking
├── connectors/
│   ├── youtube_connector.py  # YouTube Data API v3
│   ├── spotify_connector.py  # Spotify Web API
│   └── tmdb_connector.py     # Movie metadata
├── agents/
│   ├── curator_agent.py      # Main LLM agent
│   ├── preference_agent.py   # "Ignore soccer" handler
│   └── prompts/
│       ├── curator_system.txt
│       └── preference_system.txt
├── storage/
│   ├── taste_store.json      # Fingerprint
│   ├── history_log.jsonl     # Signal log
│   └── preferences.json      # User commands
├── ui/
│   └── dashboard.html
└── tests/
```
