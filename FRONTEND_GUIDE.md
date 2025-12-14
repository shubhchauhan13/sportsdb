# Frontend Developer Guide

This guide explains how to display the live cricket data from your NeonDB database.

## 1. Database Connection
You need to query the **PostgreSQL** database (NeonDB).
*   **Table Name:** `live_matches`
*   **Column:** `match_data` (Type: JSONB)

## 2. SQL Query
To get all matches, sorted by "Live" status first:

```sql
SELECT match_data 
FROM live_matches 
ORDER BY (match_data->>'is_live')::boolean DESC, last_updated DESC;
```

## 3. Data Structure (JSON)
Each row returns a JSON object. Use these fields for your UI:

```json
{
  "match_id": "XY1",
  "title": "India vs Australia",        // 1. Matches the "Title"
  "score": "132/6 (19.0)",              // 2. Main Score Display
  "status_text": "India need 20 runs",  // 3. Status/Commentary
  "is_live": true,                      // 4. If true -> Show RED "LIVE" Dot
  "match_status": "Live",               // "Live" | "Upcoming" | "Completed"
  "team_a_name": "India",               // Home Team
  "team_b_name": "Australia",           // Away Team
  "start_time_iso": "2025-12-14 16:30"  // Start Time
}
```

## 4. UI Logic Checklist
- [ ] **Live Badge:** Only show if `is_live` is `true`.
- [ ] **Score:** If `score` is null or empty, display "Match Starting Soon".
- [ ] **Refresh:** Re-run the SQL query every 1-2 seconds (or use a WebSocket if your backend supports it, but polling DB is fine for now).
