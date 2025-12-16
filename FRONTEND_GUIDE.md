
# 📚 Sports Data Frontend Guide


# 📚 Sports Data Frontend Guide

**Version**: 2.1
**Last Updated**: Dec 16, 2025

This guide details how to consume live sports data directly from the **PostgreSQL Database**.

---

## 1. System Overview

*   **Source**: Internal Database (Live Sync)
*   **Update Frequency**: Real-time (~5s latency).
*   **Data Flow**:
    `Real-time Engine` -> `PostgreSQL (NeonDB)` -> `Frontend`

## 2. Database Tables

We use **separate tables** for each sport to ensure performance and scalability.

| Sport | Table Name | Status |
| :--- | :--- | :--- |
| 🏏 **Cricket** | `live_cricket` | **Active** |
| ⚽ **Football** | `live_football` | **Active** |
| 🎾 **Tennis** | `live_tennis` | **Active** |

### Legacy Support
*   `live_matches`: Still populated for Cricket ONLY to support older app versions. New implementations should use the sport-specific tables above.

---

## 3. Table Schema

All three tables (`live_cricket`, `live_football`, `live_tennis`) share this standard schema:

| Column | Type | Description | Frontend Usage |
| :--- | :--- | :--- | :--- |
| `match_id` | `TEXT` | Unique Match ID. | Primary Key for routing/details. |
| `home_team` | `TEXT` | Name of Team A. | Display Name. |
| `away_team` | `TEXT` | Name of Team B. | Display Name. |
| `home_score` | `TEXT` | Score of Team A. | **Primary Score Display**. (Runs/Goals/Sets) |
| `away_score` | `TEXT` | Score of Team B. | **Primary Score Display**. |
| `score` | `TEXT` | Formatted Score String. | Quick display (e.g. "2 - 1" or "150/3 vs ...") |
| `status` | `TEXT` | Match Status. | **Critical**. Shows "Live", "2nd Inning", "Halftime", etc. |
| `is_live` | `BOOL` | Is match active? | Use for specific "LIVE" badges/filtering. |
| `batting_team`| `TEXT` | Name of Batting Team. | **Cricket Only**. Highlight this team. |
| `match_data` | `JSONB`| Full Raw Event Data. | Use for deep details (odds, players, events). |
| `last_updated`| `TIMESTAMP` | Sync Time. | Show "Last updated: X sec ago". |

---

## 4. Integration Logic

### A. Fetching Live Matches
To get the live leaderboard for a specific sport:

```sql
SELECT match_id, home_team, away_team, home_score, away_score, status, is_live
FROM live_cricket  -- Change table name based on sport
ORDER BY is_live DESC, last_updated DESC;
```

### B. Sport-Specific Notes

#### 🏏 Cricket
*   **Score Format**: `home_score` might be "150/3 (15.2)".
*   **Status**: We use smart logic to detect "2nd Inning" even if the API lags. Trust the `status` column.
*   **Batting Team**: Use `batting_team` column to show a "Batting" icon next to the active team.

#### ⚽ Football
*   **Score**: Simple numbers (e.g. `2`, `1`).
*   **Status**: typical values: `1st half`, `Halftime`, `2nd half`, `Ended`.

#### 🎾 Tennis
*   **Score**: Represents **Sets Won** (e.g. `1`, `0`).
*   **Deep Scores**: Parse `match_data` for game-level scores if needed (e.g. "6-4, 2-3").

---

## 5. JSON `match_data` Reference

If you need more details than the columns provide, query `match_data`.

**Key Usage Examples:**

*   **Tournament Name**: `match_data->'tournament'->>'name'`
*   **Round Info**: `match_data->'roundInfo'->>'round'`
*   **Venue**: `match_data->'venue'->>'city'`
*   **Current Period**: `match_data->'lastPeriod'` (e.g. "inning1", "period2")

### Example JSON Snippet
```json
{
  "tournament": { "name": "Big Bash League" },
  "homeTeam": { "name": "Sydney Thunder" },
  "awayTeam": { "name": "Hobart Hurricanes" },
  "homeScore": { "display": 150, "innings": {...} },
  "status": { "description": "2nd Inning", "type": "inprogress" }
}
```

---

## 6. Access & connection

*   **Database**: NeonDB
*   **Connection String**: (Refer to Env Variables)
      "runs": 132,
      "wickets": 6,
      "crr": 7.1,
      "projected_score": 142
  },
  
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


