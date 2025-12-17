# 📚 Sports Data Frontend Guide

**Version**: 3.0
**Last Updated**: Dec 17, 2025

This guide details how to consume live sports data from the **PostgreSQL Database** for **8 Supported Sports**.

---

## 1. Supported Sports & Tables

Each sport has its own dedicated table. Query the one matching your page context.

| Sport Icon | Sport | Table Name | Has Draw Odds? |
| :--- | :--- | :--- | :--- |
| 🏏 | **Cricket** | `live_cricket` | ✅ Yes (Tests) |
| ⚽ | **Football** | `live_football` | ✅ Yes |
| 🎾 | **Tennis** | `live_tennis` | ❌ No |
| 🏀 | **Basketball** | `live_basketball` | ❌ No (Usually OT) |
| 🏓 | **Table Tennis** | `live_table_tennis` | ❌ No |
| 🏒 | **Ice Hockey** | `live_ice_hockey` | ✅ Yes (Regular Time) |
| 🎮 | **Esports** | `live_esports` | ❌ No |
| 🏎️ | **Motorsport** | `live_motorsport` | ❌ No |

---

## 2. Universal Table Schema

All 8 tables share the exact same column structure for easy component reuse.

### Core Columns
| Column | Type | Description | Frontend Usage |
| :--- | :--- | :--- | :--- |
| `match_id` | `TEXT` | Unique ID | Primary Key / Routing. |
| `home_team` | `TEXT` | Team A Name | Matches "1" in Odds. |
| `away_team` | `TEXT` | Team B Name | Matches "2" in Odds. |
| `score` | `TEXT` | Formatted Score | Display string (e.g. "2 - 1", "150/3 vs 12"). |
| `status` | `TEXT` | Match Status | e.g. "Live", "Halftime", "Ended". |
| `is_live` | `BOOL` | Live Flag | Show "LIVE" badge if `true`. |
| `last_updated`| `TIMESTAMP` | Sync Time | Show "Updated Xs ago". |

### Odds Columns (New!)
Use these purely for display. Click logic should reference `match_id`.

| Column | Type | Example | Logic |
| :--- | :--- | :--- | :--- |
| `home_odds` | `TEXT` | "1.50" | Returns `X.XX` or `null`. |
| `away_odds` | `TEXT` | "2.40" | Returns `X.XX` or `null`. |
| `draw_odds` | `TEXT` | "3.20" | **Conditional Render**: Only show "Draw" button if this is NOT null. |

### Sport-Specifics
| Column | Sport | Description |
| :--- | :--- | :--- |
| `batting_team` | 🏏 Cricket | Name of the team currently batting. Show a 🏏 icon next to this team's name in the UI. |

---

## 3. Integration Examples

### A. Fetching Live Matches (SQL)
To get the live feed for Football:
```sql
SELECT 
    match_id, 
    home_team, away_team, 
    score, status, 
    home_odds, away_odds, draw_odds
FROM live_football
WHERE is_live = TRUE
ORDER BY last_updated DESC;
```

### B. React/Frontend Component Logic
Since `draw_odds` is nullable, use it to control your Grid layout.

```jsx
// Example Card Component Logic
const OddsButtons = ({ match }) => {
  return (
    <div className="grid grid-flow-col gap-2">
      {/* Home Button */}
      <button className="btn-odds">
        <span>1</span>
        <span>{match.home_odds || '-'}</span>
      </button>

      {/* Draw Button - CONDITIONAL */}
      {match.draw_odds && (
        <button className="btn-odds">
          <span>X</span>
          <span>{match.draw_odds}</span>
        </button>
      )}

      {/* Away Button */}
      <button className="btn-odds">
        <span>2</span>
        <span>{match.away_odds || '-'}</span>
      </button>
    </div>
  )
}
```

---

## 4. Cricket Specifics 🏏

Cricket requires slightly more detailed handling for a premium feel.

1.  **Format**: The `score` string is usually `Runs/Wickets (Overs)`.
2.  **Batting Indicator**: Compare `batting_team` string with `home_team` and `away_team`.
    *   If `batting_team === home_team`, highlight Home row.
    *   If `batting_team === away_team`, highlight Away row.
    *   If `batting_team` is null (e.g. Innings Break), no highlight.

---

## 5. Troubleshooting

*   **No Odds?**: The scraper inserts placeholders (e.g. 1.90) or nulls if API data is missing. Handle `null` gracefully by showing "-" or disabling the button.
*   **Stuck Data?**: Check `last_updated`. If it's > 1 minute old, the scraper might be restarting or the match is paused.
