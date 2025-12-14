# Cricket Scraper - Deployment Guide

## 1. Overview
A high-performance Python scraper that fetches live cricket scores from Crex.com and syncs them to a NeonDB (PostgreSQL) database in real-time (~1s latency).

## 2. Features
- **Real-Time Polling:** Updates every ~1 second.
- **Data Enrichment:** Decodes `^1`/`^2` status codes, maps Team IDs to Names, and calculates match states.
- **Robust Persistence:** Uses `UPSERT` to store only unique match data in JSONB format.
- **Dockerized:** Ready for deployment on Railway, Render, or DigitalOcean.

## 3. Database Schema (Schema V2)
**Table:** `live_matches`
- `match_id` (TEXT PK): Unique Match ID (e.g. `XY1`)
- `match_data` (JSONB): Full match payload.
- `last_updated` (TIMESTAMP): Last sync time.

### JSON Structure (`match_data`)
```json
{
  "match_id": "XY1",
  "title": "India vs Australia",
  "score": "132/6 (19.0)",
  "team_a_name": "India",
  "team_b_name": "Australia",
  "batting_team_name": "India",       // [NEW]
  "current_innings": "1st Innings",   // [NEW]
  "event_state": "Live",              // [NEW] "Live", "Break", "Finished"
  "league_name": "T20I",              // [NEW]
  "match_status": "Live",
  "is_live": true,
  "start_time_iso": "2025-12-14 16:30:00"
}
```

## 4. Frontend Developer Guide

### SQL Query
```sql
SELECT match_data 
FROM live_matches 
ORDER BY (match_data->>'is_live')::boolean DESC, last_updated DESC;
```

## 5. Deployment
### Render.com (Free Tier)
1. Push this repo to GitHub.
2. Create **Web Service** on Render.
3. Connect Repo.
4. Set Environment Variable: `DB_CONNECTION_STRING`.
5. **Important:** Setup UptimeRobot to ping the provided URL every 5 mins.
