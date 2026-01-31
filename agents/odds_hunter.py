"""
Odds Hunter Agent - Fill Odds Coverage Gaps

Responsibilities:
- Identify matches with missing odds
- Fetch odds from fallback sources (1xBet, Betfair, OddsPortal)
- Update database with found odds
- Prioritize critical sports (esports, table_tennis)
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core import TogetherAIClient, Agent, Tool, create_tool

import psycopg2
from psycopg2.extras import Json
import requests

logger = logging.getLogger("OddsHunterAgent")

# =============================================================================
# Configuration
# =============================================================================

DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING",
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Priority sports for odds hunting (highest missing rates first)
PRIORITY_SPORTS = ["esports", "table_tennis", "snooker", "badminton", "handball", "cricket"]

# Odds sources configuration
ODDS_SOURCES = {
    "sofascore_api": {
        "enabled": True,
        "base_url": "https://www.sofascore.com/api/v1",
    },
    # More sources can be added here
}


# =============================================================================
# Tool Functions
# =============================================================================

def get_matches_without_odds(sport: str, limit: int = 20) -> str:
    """
    Get live matches that are missing odds for a sport.
    
    Args:
        sport: Sport name
        limit: Maximum number of matches to return
    
    Returns:
        JSON string of matches needing odds
    """
    table_name = f"live_{sport}"
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        cur.execute(f"""
            SELECT match_id, home_team, away_team, status, score, match_data
            FROM {table_name}
            WHERE is_live = TRUE
            AND (
                other_odds IS NULL 
                OR other_odds::text = '{{}}'
                OR other_odds::text = 'null'
            )
            ORDER BY last_updated DESC
            LIMIT %s
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        
        matches = []
        for row in rows:
            match_id, home, away, status, score, data = row
            matches.append({
                "match_id": match_id,
                "home_team": home,
                "away_team": away,
                "status": status,
                "score": score,
                # Include source_id if available (for API lookup)
                "source_id": data.get("id") if isinstance(data, dict) else None
            })
        
        if not matches:
            return f"No matches without odds found for {sport}"
        
        return json.dumps(matches, indent=2)
        
    except Exception as e:
        return f"Failed to query matches: {str(e)}"


def fetch_sofascore_odds(event_id: str) -> str:
    """
    Fetch odds from Sofascore API for a specific event.
    
    Args:
        event_id: Sofascore event ID
    
    Returns:
        Odds data or error message
    """
    if not event_id or not str(event_id).isdigit():
        return f"Invalid event ID: {event_id}"
    
    # Clean the ID (remove prefixes like 'sf_')
    clean_id = str(event_id).replace("sf_", "").replace("sfb_", "").replace("sfv_", "")
    
    url = f"https://www.sofascore.com/api/v1/event/{clean_id}/odds/1/all"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 404:
            return f"No odds available for event {clean_id}"
        
        if resp.status_code != 200:
            return f"Sofascore API error: HTTP {resp.status_code}"
        
        data = resp.json()
        markets = data.get("markets", [])
        
        if not markets:
            return f"No odds markets found for event {clean_id}"
        
        # Extract main market (usually 'Winner' or 'Full time')
        for market in markets:
            if market.get("isMain") or market.get("marketName") in ["Winner", "Match Winner", "Full time"]:
                choices = market.get("choices", [])
                if len(choices) >= 2:
                    odds = {
                        "home": choices[0].get("fractionalValue") or choices[0].get("decimalValue"),
                        "away": choices[1].get("fractionalValue") or choices[1].get("decimalValue"),
                        "draw": choices[2].get("fractionalValue") if len(choices) > 2 else None,
                        "source": "sofascore",
                        "fetched_at": datetime.now().isoformat()
                    }
                    return json.dumps(odds)
        
        return "Could not parse odds from response"
        
    except Exception as e:
        return f"Failed to fetch odds: {str(e)}"


def update_match_odds(sport: str, match_id: str, odds_json: str) -> str:
    """
    Update odds for a specific match in the database.
    
    Args:
        sport: Sport name
        match_id: Match ID to update
        odds_json: JSON string of odds data
    
    Returns:
        Status message
    """
    table_name = f"live_{sport}"
    
    try:
        odds = json.loads(odds_json)
    except json.JSONDecodeError:
        return f"Invalid odds JSON: {odds_json}"
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        cur.execute(f"""
            UPDATE {table_name}
            SET 
                other_odds = COALESCE(other_odds, '{{}}'::jsonb) || %s::jsonb,
                home_odds = COALESCE(home_odds, %s),
                away_odds = COALESCE(away_odds, %s),
                draw_odds = COALESCE(draw_odds, %s),
                last_updated = NOW()
            WHERE match_id = %s
        """, (
            Json(odds),
            odds.get("home"),
            odds.get("away"),
            odds.get("draw"),
            match_id
        ))
        
        updated = cur.rowcount
        conn.commit()
        conn.close()
        
        if updated > 0:
            return f"Updated odds for match {match_id}"
        else:
            return f"No match found with ID {match_id}"
            
    except Exception as e:
        return f"Failed to update odds: {str(e)}"


def get_odds_coverage_summary() -> str:
    """
    Get a summary of odds coverage across all sports.
    
    Returns:
        Coverage summary string
    """
    sports_tables = [
        "live_football", "live_cricket", "live_basketball", "live_tennis",
        "live_table_tennis", "live_ice_hockey", "live_esports", "live_volleyball"
    ]
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        results = []
        critical = []
        
        for table in sports_tables:
            sport = table.replace("live_", "")
            try:
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE other_odds IS NOT NULL AND other_odds::text != '{{}}') as with_odds
                    FROM {table}
                    WHERE is_live = TRUE
                """)
                row = cur.fetchone()
                total, with_odds = row
                
                if total > 0:
                    coverage = round((with_odds / total) * 100, 1)
                    status = "✓" if coverage > 80 else "!" if coverage > 50 else "✗"
                    results.append(f"{status} {sport}: {coverage}% ({with_odds}/{total})")
                    if coverage < 50:
                        critical.append(sport)
                else:
                    results.append(f"- {sport}: No live matches")
                    
            except Exception:
                results.append(f"? {sport}: Error")
        
        conn.close()
        
        summary = "Odds Coverage Summary:\n" + "\n".join(results)
        if critical:
            summary += f"\n\nCRITICAL (< 50%): {', '.join(critical)}"
        
        return summary
        
    except Exception as e:
        return f"Failed to get coverage: {str(e)}"


def hunt_odds_for_sport(sport: str, max_matches: int = 10) -> str:
    """
    Automatically hunt and fill odds for a sport.
    
    Args:
        sport: Sport to hunt odds for
        max_matches: Maximum matches to process
    
    Returns:
        Summary of results
    """
    results = []
    success = 0
    failed = 0
    
    # Get matches without odds
    matches_json = get_matches_without_odds(sport, max_matches)
    if matches_json.startswith("No matches") or matches_json.startswith("Failed"):
        return matches_json
    
    try:
        matches = json.loads(matches_json)
    except json.JSONDecodeError:
        return f"Failed to parse matches: {matches_json}"
    
    for match in matches:
        match_id = match.get("match_id")
        source_id = match.get("source_id")
        
        if not source_id:
            results.append(f"  {match_id}: No source ID, skipping")
            continue
        
        # Try to fetch odds
        odds_result = fetch_sofascore_odds(str(source_id))
        
        if odds_result.startswith("{"):  # Valid JSON odds
            # Update database
            update_result = update_match_odds(sport, match_id, odds_result)
            if "Updated" in update_result:
                success += 1
                results.append(f"  {match['home_team']} vs {match['away_team']}: ✓")
            else:
                failed += 1
                results.append(f"  {match_id}: Update failed")
        else:
            failed += 1
            results.append(f"  {match['home_team']} vs {match['away_team']}: No odds found")
        
        # Rate limiting
        time.sleep(0.5)
    
    summary = f"Odds Hunt for {sport}: {success}/{len(matches)} successful"
    return summary + "\n" + "\n".join(results[:10])  # Limit output


# =============================================================================
# Odds Hunter Agent Class
# =============================================================================

class OddsHunterAgent(Agent):
    """
    Agent that proactively fills odds gaps.
    
    Focuses on sports with poor coverage and actively fetches from multiple sources.
    """
    
    def __init__(self, client: TogetherAIClient, model: str = None):
        super().__init__(client, model)
        self._register_tools()
    
    def _register_tools(self):
        """Register all odds hunting tools."""
        
        self.add_tool(create_tool(
            name="get_odds_coverage_summary",
            description="Get a summary of odds coverage across all sports to identify priorities",
            parameters={},
            function=get_odds_coverage_summary
        ))
        
        self.add_tool(create_tool(
            name="get_matches_without_odds",
            description="Get list of live matches that are missing odds for a sport",
            parameters={
                "sport": {"type": "string", "description": "Sport name (e.g., 'esports', 'table_tennis')"},
                "limit": {"type": "integer", "description": "Max matches to return (default 20)"}
            },
            function=get_matches_without_odds
        ))
        
        self.add_tool(create_tool(
            name="fetch_sofascore_odds",
            description="Fetch odds from Sofascore API for a specific event ID",
            parameters={
                "event_id": {"type": "string", "description": "Sofascore event ID (numeric)"}
            },
            function=fetch_sofascore_odds
        ))
        
        self.add_tool(create_tool(
            name="update_match_odds",
            description="Update odds for a match in the database",
            parameters={
                "sport": {"type": "string", "description": "Sport name"},
                "match_id": {"type": "string", "description": "Match ID to update"},
                "odds_json": {"type": "string", "description": "JSON string with odds data"}
            },
            function=update_match_odds
        ))
        
        self.add_tool(create_tool(
            name="hunt_odds_for_sport",
            description="Automatically hunt and fill odds for a sport (batch process)",
            parameters={
                "sport": {"type": "string", "description": "Sport to hunt odds for"},
                "max_matches": {"type": "integer", "description": "Max matches to process (default 10)"}
            },
            function=hunt_odds_for_sport
        ))
    
    def get_system_prompt(self) -> str:
        return """You are the Odds Hunter Agent for a live sports betting data platform.

Your mission: FILL THE GAPS in odds coverage.

Current priority sports (highest missing rates):
1. esports (98% missing)
2. table_tennis (97% missing)
3. snooker (80% missing)
4. badminton (62% missing)
5. cricket (40% missing)

When activated:
1. First check overall coverage with get_odds_coverage_summary
2. Pick the sport with worst coverage
3. Get matches without odds for that sport
4. For each match with a source_id, fetch odds from Sofascore
5. Update the database with found odds
6. Report results

Use hunt_odds_for_sport for batch processing when you want to fill many matches quickly.

Your goal is to maximize odds coverage. Every percentage point matters!"""


def run_odds_hunter_loop(interval_seconds: int = 300):
    """
    Run the Odds Hunter Agent in a loop.
    
    Args:
        interval_seconds: How often to run (default 5 min)
    """
    logger.info("Starting Odds Hunter loop...")
    
    client = TogetherAIClient()
    agent = OddsHunterAgent(client)
    
    while True:
        try:
            logger.info("=" * 50)
            logger.info("Running Odds Hunt...")
            
            result = agent.run("Check odds coverage and hunt for missing odds. Focus on the sport with the worst coverage.")
            
            logger.info(f"Hunt Result:\n{result}")
            
        except Exception as e:
            logger.error(f"Odds hunter error: {e}")
        
        logger.info(f"Sleeping for {interval_seconds}s...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds")
    parser.add_argument("--sport", type=str, help="Hunt odds for a specific sport")
    args = parser.parse_args()
    
    if args.loop:
        run_odds_hunter_loop(args.interval)
    elif args.sport:
        client = TogetherAIClient()
        agent = OddsHunterAgent(client)
        result = agent.run(f"Hunt odds for {args.sport} and update as many matches as possible.")
        print(result)
    else:
        # Quick test
        client = TogetherAIClient()
        agent = OddsHunterAgent(client)
        result = agent.run("Check odds coverage and identify which sport needs help the most.")
        print(result)
