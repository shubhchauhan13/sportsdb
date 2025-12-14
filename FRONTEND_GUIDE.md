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
  "event_state": "Live",                // [NEW] "Live" | "Break" | "Finished" | "Scheduled"
  "team_a_name": "India",               // Home Team
  "team_b_name": "Australia",           // Away Team
  "batting_team_name": "India",         // [NEW] Name of batting team
  "current_innings": "1st Innings",     // [NEW] e.g. "2nd Innings"
  "league_name": "T20I",                // [NEW] Format or League Name
  "match_odds": {                       // [NEW]
      "team_a_odds": 1.5,
      "team_b_odds": 2.5,
      "team_a_win_prob": 66.6,
      "team_b_win_prob": 33.3
  },
  "session": {                          // [NEW] Only present if Live
      "runs": 132,
      "wickets": 6,
      "crr": 7.1,
      "projected_score": 142
  },
  "start_time_iso": "2025-12-14 16:30", // Start Time
  
  // [NEW] Detailed Scores & Target
  "team_a_score": "132/6 (20.0)",       // Score of Team A
  "team_b_score": "50/1 (4.2)",         // Score of Team B
  "target": "134"                       // Target score (if 2nd Innings)
}

```

## 4. UI Logic Checklist
- [ ] **Live Badge:** Only show if `is_live` is `true`.
- [ ] **Batting Indicator:** Show a bat icon next to `batting_team_name`.
- [ ] **State:** Use `event_state` for chips (e.g. "Drinks Break", "Innings Break").
- [ ] **Score:** If `score` is null or empty, display "Match Starting Soon".

- [ ] **Refresh:** Re-run the SQL query every 1-2 seconds (or use a WebSocket if your backend supports it, but polling DB is fine for now).

## 5. UI Component Mapping (Example)
If you are building a card component, map the data like this:

| UI Element | JSON Field | Logic |
| :--- | :--- | :--- |
| **Card Header** | `league_name` | Fallback to `format` if empty. |
| **Badge** | `event_state` | Red for "Live", Orange for "Break", Grey for "Finished". |
| **Team 1** | `team_a_name` | Bold if `batting_team_name` matches. |
| **Team 2** | `team_b_name` | Bold if `batting_team_name` matches. |
| **Big Score** | `score` | Show `--/--` if empty. |
| **Status Text** | `status_text` | e.g. "Need 15 runs to win". |
| **Footer** | `current_innings` | e.g. "1st Innings". |

## 6. Betting Odds (New)
If `match_odds` is not null:
- **Odds A:** `match_odds.team_a_odds` (e.g. 1.50)
- **Odds B:** `match_odds.team_b_odds` (e.g. 2.50)
- **Win Prob:** Show a progress bar using `match_odds.team_a_win_prob` %.

## 7. Session/Fancy (New)
If `session` is not null (Live matches only):
- **CRR:** `session.crr` (Current Run Rate)
- **Projected Score:** `session.projected_score` (Estimated final score)


