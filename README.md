# 🏠 Personal Hub

A NiceGUI-powered personal dashboard with three tabs:

| Tab | What it does |
|-----|-------------|
| 🏟️ **Matchday** | Live sports schedules — EPL, UCL, LCK, MLB, KBO |
| 🎯 **Career** | Career goals tracker with status, categories, deadlines |
| 🚀 **Projects** | Personal project workspace with task checklists |

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Run
python main.py

# 3. Open
# → http://localhost:8080
```

## Project Structure

```
personal-hub/
├── main.py           # App entry point + all 3 tabs
├── sports_data.py    # Sports data provider (demo → swap for APIs)
├── requirements.txt
└── README.md
```

## Making Sports Data Live

The `sports_data.py` file has placeholder functions for real APIs:

| League | API | Auth |
|--------|-----|------|
| EPL / UCL | [api-football.com](https://www.api-football.com) | Free key (100 req/day) |
| LCK | Community APIs / lolesports | No key |
| MLB | [statsapi.mlb.com](https://statsapi.mlb.com) | Free, no key |
| KBO | Scraping / manual | N/A |

## Data Persistence

Currently uses `app.storage.general` (server-side dict persisted to `.nicegui/`).
For multi-device access, swap for SQLite or a JSON file.

## Deployment

```bash
# Docker
docker build -t personal-hub .
docker run -p 8080:8080 personal-hub

# Or Cloud Run (you already know this one)
gcloud run deploy personal-hub --source . --port 8080
```
