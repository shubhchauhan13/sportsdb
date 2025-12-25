
# Implementation Plan - Fixing Missing Odds

## Goal
Fix the high percentage of missing odds in **Table Tennis** (96.7%) and **Esports** (98.4%), and improve odds extraction robustness across all sports to achieve "100% bulletproof" data quality.

## Problem Analysis
- **Table Tennis**: 5553/5742 matches have null odds.
- **Esports**: 313/318 matches have null odds.
- **Root Cause Hypothesis**:
    1. **Extraction Failure**: The odds exist in the raw JSON/HTML but our parser is looking in the wrong place (e.g., changed API keys, different structure for these sports).
    2. **Source Data Missing**: The source (e.g., Sofascore, Flashscore, etc.) isn't providing odds on the summary list we are fetching.

## Proposed Changes

### Phase 1: Table Tennis Fix (Highest Volume)
1. **Diagnose Raw Data**:
   - Create `debug_table_tennis.py` to inspect `match_data` column in `live_table_tennis`.
   - Check if odds information exists nested deep within the JSON (e.g., `structure`, `odds`, `markets`).
2. **Update Extraction Logic**:
   - Modify `scraper_service.py` (or specific sport handler) to correctly extract odds from the discovered path.
   - If odds are missing from list view, implement a "Detail Fetch" fallback (if consistent with architecture) or switch to a better source endpoint for this sport.

### Phase 2: Esports Fix
1. **Diagnose Raw Data**:
   - Similar diagnosis for `live_esports`. Esports often has complex nested structures for maps/rounds.
2. **Update Extraction Logic**:
   - Adjust parsing logic to handle Esports-specific structures.

### Phase 3: "Bulletproof" System (General Robustness)
1. **Generic Odds Extractor**: 
   - Implement a more aggressive recursive search for "odds-like" keys (`odds`, `avgOdds`, `choices`) in the raw data if the standard path fails.
2. **Validation**:
   - Run `deep_checks.py` again to verify the drop in missing odds.

## Verification Plan
### Automated Tests
- Run `deep_checks.py` to compare before/after stats.
- Create `verify_fix_odds.py` to print sample odds for previously null matches.

### Manual Verification
- Check the database for populated `other_odds` columns.
