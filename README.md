# Crex.com WebSocket/API Interceptor

## Overview
We successfully reverse-engineered the data flow of **Crex.com**. Contrary to the initial assumption of WebSockets, the site relies heavily on **XHR polling** to `api-v1.com` for its live match data (specifically the `liveMatches2.php` endpoint) or uses a mechanism that is best intercepted via HTTP response monitoring.

We have delivered a robust **Python Relay Script** that uses a Headless Browser to stealthily load the site, intercept these background data packets, and forward them to your local API.

## Deliverables

### 1. Relay Script (`relay_server.py`)
This is the core "Listener" service.

**Features:**
*   **Headless Browser:** Uses Playwright (Chromium) to match a real user environment.
*   **Stealth Headers:** Automatically injects `Origin` and `Referer` to ensure upstream APIs respond correctly.
*   **Auto-Interception:** Listens for *any* background response from `api-v1.com` containing live match data.
*   **Resilience:** Auto-reloads the page every 10 minutes to refresh tokens and session headers.
*   **Forwarding:** POSTs the intercepted JSON payload to `http://localhost:8000/ingest` (configurable).

**Usage:**
```bash
pip install playwright requests
playwright install
python3 relay_server.py
```

### 2. Sample Data (`sample_data.json`)
A real captured payload from the `liveMatches` endpoint.

**Structure Highlight:**
*   The root object contains keys like `WQF`, `X0T` (Match IDs).
*   Inside each match:
    *   `j`: Score string (e.g., `"137/5(20.0)"`).
    *   `mm`: Commentary/Status (e.g., `"Hobart Hurricanes Women won by..."`).
    *   `ti`: Timestamp.

## Next Steps
1.  **Deploy:** Run `relay_server.py` on your server.
2.  **Ingest:** Ensure your API at `localhost:8000/ingest` processes the JSON schema shown in `sample_data.json`.
3.  **Scale:** If needed, run multiple instances for different target pages, though the Home Page ticker usually captures all active matches.

## Deployment Guide (Easiest Method: Railway)

We recommend **Railway.app** because it automatically detects the `Dockerfile` and requires zero configuration.

1.  **Push to GitHub:** Upload your code (including `Dockerfile` and `requirements.txt`) to a GitHub repository.
2.  **Railway:**
    *   Go to [railway.app](https://railway.app/) -> "New Project" -> "Deploy from GitHub repo".
    *   Select your repository.
    *   It will start building automatically.
3.  **Variables:**
    *   Go to the "Variables" tab in Railway.
    *   Add `DB_CONNECTION_STRING` = `postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
4.  **Done:** Your scraper is now live 24/7.


### Setup Instructions
1.  Go to the [Firebase Console](https://console.firebase.google.com/).
2.  Create a project -> **Build** -> **Realtime Database** -> **Create Database** (Start in Test Mode).
3.  Go to **Project Settings** -> **Service Accounts** -> **Generate New Private Key**.
4.  Save the file as `serviceAccountKey.json` in this directory.
5.  Open `scraper_service.py` and update the `FIREBASE_DB_URL` at the top with your database URL (e.g., `https://your-project.firebaseio.com/`).
### Database Schema (NeonDB)

The `live_matches` table stores the cleaned data:

```sql
match_id (TEXT PRIMARY KEY)
match_data (JSONB)
last_updated (TIMESTAMP)
```

**JSON Structure (`match_data`):**
```json
{
  "match_id": "XY1",
  "title": "India vs Australia",
  "is_live": true,
  "match_status": "Live",   // Decoded from '^2'
  "status_text": "In Progress",
  "score": "132/6(19.0)",
  "team_a": "1DY",
  "team_b": "1DZ",
  "team_a_name": "India",   // Enriched from Lookup
  "team_b_name": "Australia",
  "start_time_iso": "2025-12-14 16:30:00",
  "raw": { ... }
}
```

To see only live matches:
```sql
SELECT * FROM live_matches WHERE match_data->>'is_live' = 'true';
```

