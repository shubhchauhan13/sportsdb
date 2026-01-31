"""
Cricket Session Odds Scraper

Fetches session/fancy odds from multiple sources:
1. CricBuzz Live API (unofficial)
2. Betfair Exchange (via web scraping)
3. Direct 1xBet API endpoint (hidden)

Session markets include:
- 6 Over Runs (Lambi/Khai)
- First Innings Runs
- Session Runs (5/10/15 overs)
"""

import os
import sys
import json
import re
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
import psycopg2
from psycopg2.extras import Json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionOddsScraper")

DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING",
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# =============================================================================
# Source 1: CricBuzz API (Unofficial - get match data)
# =============================================================================

def fetch_cricbuzz_live_matches() -> List[Dict]:
    """
    Fetch live cricket matches from CricBuzz's unofficial API.
    """
    matches = []
    try:
        # CricBuzz uses this endpoint for live data
        url = "https://www.cricbuzz.com/api/cricket-match/commentary/"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        }
        
        # First get live matches list
        list_url = "https://www.cricbuzz.com/api/html/homepage-scag"
        resp = requests.get(list_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            # Parse the response for match IDs
            # This is HTML, so we extract match IDs using regex
            match_ids = re.findall(r'/live-cricket-scores/(\d+)/', resp.text)
            unique_ids = list(set(match_ids))[:10]  # Limit to 10
            
            logger.info(f"CricBuzz: Found {len(unique_ids)} live match IDs")
            
            for mid in unique_ids:
                try:
                    detail_url = f"https://www.cricbuzz.com/api/cricket-match/{mid}/commentary"
                    detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                    if detail_resp.status_code == 200:
                        data = detail_resp.json()
                        match_info = data.get("matchInfo", {})
                        matches.append({
                            "match_id": f"cb_{mid}",
                            "source": "cricbuzz",
                            "home_team": match_info.get("team1", {}).get("name", ""),
                            "away_team": match_info.get("team2", {}).get("name", ""),
                            "status": match_info.get("status", ""),
                            "venue": match_info.get("venue", {}).get("name", ""),
                            "raw_data": data
                        })
                except Exception as e:
                    logger.debug(f"CricBuzz match {mid} error: {e}")
                    
    except Exception as e:
        logger.error(f"CricBuzz fetch error: {e}")
    
    return matches


# =============================================================================
# Source 2: 1xBet Hidden API (Session Markets)
# =============================================================================

def fetch_1xbet_cricket_odds() -> Dict[str, Dict]:
    """
    Fetch cricket session odds from 1xBet's internal API.
    
    Returns dict mapping match names to session odds.
    """
    session_odds = {}
    
    try:
        # 1xBet cricket live endpoint (discovered via network inspection)
        url = "https://1xbet.com/LiveFeed/Get1702?count=50&lng=en&mode=4&country=1&partner=51&getEmpty=true&sports=3"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://1xbet.com/en/live/cricket"
        }
        
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("Value", [])
            
            logger.info(f"1xBet: Found {len(events)} cricket events")
            
            for event in events:
                try:
                    match_name = f"{event.get('O1', 'Team A')} vs {event.get('O2', 'Team B')}"
                    match_id = str(event.get("I", ""))
                    
                    # Extract odds from event
                    odds_data = {
                        "match_id": f"1x_{match_id}",
                        "match_name": match_name,
                        "match_winner": {},
                        "session_odds": []
                    }
                    
                    # Parse GE (Game Events - contains markets)
                    game_events = event.get("GE", [])
                    for ge in game_events:
                        market_name = ge.get("G", "")  # Market group
                        market_type = ge.get("T", 0)   # Market type ID
                        
                        # Look for session markets
                        # Type 17 = Total Runs, Type 918 = Session markets
                        if "Over" in market_name or "Runs" in market_name or "Session" in market_name:
                            outcomes = ge.get("E", [])
                            parsed_outcomes = []
                            
                            for outcome in outcomes:
                                parsed_outcomes.append({
                                    "name": outcome.get("T", ""),
                                    "odds": outcome.get("C", 0),
                                    "param": outcome.get("P", "")
                                })
                            
                            if parsed_outcomes:
                                odds_data["session_odds"].append({
                                    "market": market_name,
                                    "outcomes": parsed_outcomes
                                })
                        
                        # Match winner odds (1X2 type)
                        if market_type == 1:
                            outcomes = ge.get("E", [])
                            for outcome in outcomes:
                                name = outcome.get("T", "")
                                coef = outcome.get("C", 0)
                                if "1" in name or "home" in name.lower():
                                    odds_data["match_winner"]["home"] = coef
                                elif "2" in name or "away" in name.lower():
                                    odds_data["match_winner"]["away"] = coef
                                elif "X" in name or "draw" in name.lower():
                                    odds_data["match_winner"]["draw"] = coef
                    
                    if odds_data["session_odds"] or odds_data["match_winner"]:
                        session_odds[match_name] = odds_data
                        
                except Exception as e:
                    logger.debug(f"1xBet event parse error: {e}")
                    
    except Exception as e:
        logger.error(f"1xBet fetch error: {e}")
    
    return session_odds


# =============================================================================
# Source 3: Betfair (Exchange Fancy Markets) - via API
# =============================================================================

def fetch_betfair_session_odds() -> Dict[str, Dict]:
    """
    Fetch session/fancy market odds from Betfair Exchange.
    
    Note: Requires Betfair API credentials for full access.
    This uses the public exchange data where available.
    """
    session_odds = {}
    
    try:
        # Betfair's public cricket endpoint
        url = "https://www.betfair.com/www/sports/navigation/facet/v1/search"
        params = {
            "facet": "LIVE",
            "type": "SPORT",
            "sportId": "4",  # Cricket
            "maxResults": "50"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json"
        }
        
        # Note: Public endpoint limited, but we try
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200 and resp.content:
            try:
                data = resp.json()
                events = data.get("attachments", {}).get("events", {})
                
                for event_id, event_data in events.items():
                    match_name = event_data.get("name", "")
                    session_odds[match_name] = {
                        "match_id": f"bf_{event_id}",
                        "match_name": match_name,
                        "source": "betfair",
                        "markets": []
                    }
            except json.JSONDecodeError:
                pass
                
    except Exception as e:
        logger.error(f"Betfair fetch error: {e}")
    
    return session_odds


# =============================================================================
# Database Integration
# =============================================================================

def update_cricket_session_odds(session_data: Dict):
    """
    Update live_cricket table with session odds data.
    """
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        updated_count = 0
        
        for match_name, odds_data in session_data.items():
            # Try to find matching cricket match by team names
            teams = match_name.split(" vs ")
            if len(teams) != 2:
                continue
                
            home_team = teams[0].strip()
            away_team = teams[1].strip()
            
            # Fuzzy match - look for partial team name match
            cur.execute("""
                UPDATE live_cricket
                SET 
                    other_odds = COALESCE(other_odds, '{}'::jsonb) || %s::jsonb,
                    last_updated = NOW()
                WHERE 
                    (home_team ILIKE %s OR home_team ILIKE %s)
                    AND (away_team ILIKE %s OR away_team ILIKE %s)
                    AND is_live = TRUE
                RETURNING match_id
            """, (
                Json({
                    "session_odds": odds_data.get("session_odds", []),
                    "source": "1xbet",
                    "updated_at": datetime.now().isoformat()
                }),
                f"%{home_team[:6]}%", f"%{home_team.split()[-1]}%",
                f"%{away_team[:6]}%", f"%{away_team.split()[-1]}%"
            ))
            
            if cur.rowcount > 0:
                updated_count += cur.rowcount
                logger.info(f"Updated session odds for: {match_name}")
        
        conn.commit()
        conn.close()
        
        return updated_count
        
    except Exception as e:
        logger.error(f"DB update error: {e}")
        return 0


# =============================================================================
# Main
# =============================================================================

def fetch_all_session_odds() -> Dict:
    """
    Fetch session odds from all sources and aggregate.
    """
    all_odds = {}
    
    # Source 1: 1xBet (best for session markets)
    logger.info("Fetching 1xBet session odds...")
    xbet_odds = fetch_1xbet_cricket_odds()
    all_odds.update(xbet_odds)
    logger.info(f"1xBet: Got odds for {len(xbet_odds)} matches")
    
    # Source 2: Betfair
    logger.info("Fetching Betfair session odds...")
    bf_odds = fetch_betfair_session_odds()
    # Merge without overwriting 1xbet data
    for k, v in bf_odds.items():
        if k not in all_odds:
            all_odds[k] = v
    logger.info(f"Betfair: Got odds for {len(bf_odds)} matches")
    
    return all_odds


def run_session_odds_scraper():
    """
    Main function to fetch and update session odds.
    """
    logger.info("=" * 50)
    logger.info("CRICKET SESSION ODDS SCRAPER")
    logger.info("=" * 50)
    
    # Fetch from all sources
    session_data = fetch_all_session_odds()
    
    if not session_data:
        logger.warning("No session odds found from any source")
        return
    
    logger.info(f"Total matches with session data: {len(session_data)}")
    
    # Print summary
    for match_name, odds in list(session_data.items())[:5]:
        session_count = len(odds.get("session_odds", []))
        logger.info(f"  {match_name}: {session_count} session markets")
        for so in odds.get("session_odds", [])[:2]:
            logger.info(f"    - {so.get('market')}: {len(so.get('outcomes', []))} outcomes")
    
    # Update database
    updated = update_cricket_session_odds(session_data)
    logger.info(f"Updated {updated} cricket matches with session odds")
    
    return session_data


if __name__ == "__main__":
    run_session_odds_scraper()
