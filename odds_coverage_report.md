
# Deep Database Odds Analysis Report

## 1. Summary Findings

*   **Total Matches Analyzed:** 12,889
*   **Matches with Missing Odds:** 7,644 (59.3%)
*   **Sports with 100% Missing Odds:** None (among sports with >0 matches).
*   **Sports with Critical Data Loss (>95%):**
    *   `live_esports`: 98.4% missing (313/318 matches)
    *   `live_table_tennis`: 96.7% missing (5553/5742 matches)

## 2. Detailed Breakdown by Sport

| Sport Table | Total Matches | Matches w/ Null Odds | % Missing |
| :--- | :--- | :--- | :--- |
| **live_table_tennis** | 5,742 | 5,553 | **96.7%** |
| **live_basketball** | 2,191 | 382 | 17.4% |
| **live_football** | 1,940 | 339 | 17.5% |
| **live_ice_hockey** | 1,077 | 512 | 47.5% |
| **live_tennis** | 548 | 113 | 20.6% |
| **live_volleyball** | 468 | 139 | 29.7% |
| **live_handball** | 332 | 180 | 54.2% |
| **live_esports** | 318 | 313 | **98.4%** |
| **live_baseball** | 101 | 44 | 43.6% |
| **live_cricket** | 97 | 39 | 40.2% |
| **live_badminton** | 39 | 24 | 61.5% |
| **live_american_football** | 31 | 2 | 6.5% |
| **live_snooker** | 5 | 4 | 80.0% |
| **live_motorsport** | 0 | 0 | - |
| **live_rugby** | 0 | 0 | - |
| **live_water_polo** | 0 | 0 | - |

## 3. Methodology
*   Referenced all `live_*` tables in the database.
*   Checked for presence of valid odds in `other_odds` (JSON) and legacy columns (`home_odds`, `away_odds`).
*   Considered "Null Odds" if `other_odds` is NULL/empty AND legacy columns are NULL/empty/placeholder.
*   **Note:** `live_esports` and `live_table_tennis` show extremely high rates of missing data, indicating a potential scraper or data source issue for these specific sports.
