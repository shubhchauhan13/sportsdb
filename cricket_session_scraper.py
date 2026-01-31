"""
Cricket Session Odds Scraper - Playwright Version

Uses browser automation to scrape session/fancy odds from:
1. CrickBuzz (ball-by-ball, commentary, session info)
2. Bet365 Live Cricket (session markets)
"""

import os
import sys
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import Json
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CricketSessionScraper")

DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING",
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)


def scrape_cricbuzz_session_data(headless: bool = True) -> List[Dict]:
    """
    Scrape live cricket matches from CricBuzz and extract session info.
    """
    matches = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        page = context.new_page()
        
        try:
            # Step 1: Get list of live matches
            logger.info("Fetching CricBuzz live matches...")
            page.goto("https://www.cricbuzz.com/cricket-match/live-scores", timeout=30000)
            page.wait_for_timeout(3000)
            
            # Find all live match links
            match_links = page.locator("a[href*='/live-cricket-scores/']").all()
            unique_links = []
            seen = set()
            
            for link in match_links[:15]:  # Limit to 15 matches
                href = link.get_attribute("href")
                if href and href not in seen and "/live-cricket-scores/" in href:
                    seen.add(href)
                    unique_links.append(href)
            
            logger.info(f"Found {len(unique_links)} live matches")
            
            # Step 2: Visit each match for detailed data
            for href in unique_links[:5]:  # Process top 5
                try:
                    full_url = f"https://www.cricbuzz.com{href}" if href.startswith("/") else href
                    logger.info(f"Processing: {full_url}")
                    
                    page.goto(full_url, timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # Extract match info
                    title = page.title()
                    match_name = title.split(" - ")[0] if " - " in title else title
                    
                    # Get teams from the page
                    teams_text = page.locator(".cb-nav-subhdr").first.inner_text() if page.locator(".cb-nav-subhdr").count() > 0 else match_name
                    
                    # Extract score
                    score_elements = page.locator(".cb-min-bat-rw").all()
                    scores = []
                    for el in score_elements[:2]:
                        scores.append(el.inner_text())
                    
                    # Look for session/over data in commentary
                    body_text = page.inner_text("body")
                    
                    # Extract over-by-over data using patterns
                    session_info = {
                        "powerplay_runs": None,
                        "current_over": None,
                        "run_rate": None,
                        "projected_score": None
                    }
                    
                    # Find run rate
                    rr_match = re.search(r"Run rate:\s*([\d.]+)", body_text, re.IGNORECASE)
                    if rr_match:
                        session_info["run_rate"] = float(rr_match.group(1))
                    
                    # Find current over
                    over_match = re.search(r"(\d+\.\d+)\s*overs?", body_text, re.IGNORECASE)
                    if over_match:
                        session_info["current_over"] = float(over_match.group(1))
                    
                    # Estimate session odds based on run rate
                    # This is a calculated value, not actual betting odds
                    if session_info["run_rate"]:
                        rr = session_info["run_rate"]
                        # 6 over predicted runs
                        session_info["6_over_predicted"] = round(rr * 6, 1)
                        # 10 over predicted runs
                        session_info["10_over_predicted"] = round(rr * 10, 1)
                        # 20 over predicted runs
                        session_info["20_over_predicted"] = round(rr * 20, 1)
                    
                    # Try to get actual odds if available on page
                    # Look for betting-related text
                    if "odds" in body_text.lower():
                        odds_section = re.search(r"Odds[:\s]+([0-9.]+)", body_text, re.IGNORECASE)
                        if odds_section:
                            session_info["match_odds_found"] = odds_section.group(1)
                    
                    match_data = {
                        "source": "cricbuzz",
                        "match_name": match_name,
                        "teams": teams_text,
                        "scores": scores,
                        "session_info": session_info,
                        "url": full_url,
                        "scraped_at": datetime.now().isoformat()
                    }
                    
                    matches.append(match_data)
                    logger.info(f"  Got session data: RR={session_info.get('run_rate')}, Over={session_info.get('current_over')}")
                    
                except Exception as e:
                    logger.warning(f"Error processing match: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"CricBuzz scrape error: {e}")
        finally:
            browser.close()
    
    return matches


def scrape_flashscore_cricket_odds(headless: bool = True) -> List[Dict]:
    """
    Scrape cricket odds from FlashScore (alternative to blocked sites).
    """
    matches = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        try:
            logger.info("Fetching FlashScore cricket...")
            page.goto("https://www.flashscore.com/cricket/", timeout=60000)
            page.wait_for_timeout(5000)
            
            # Look for live matches
            live_matches = page.locator(".event__match--live").all()
            logger.info(f"Found {len(live_matches)} live cricket matches on FlashScore")
            
            for match_el in live_matches[:10]:
                try:
                    home = match_el.locator(".event__participant--home").inner_text()
                    away = match_el.locator(".event__participant--away").inner_text()
                    score = match_el.locator(".event__score").inner_text() if match_el.locator(".event__score").count() > 0 else ""
                    
                    # Try to get odds
                    odds_els = match_el.locator(".odds__odd").all()
                    odds = {}
                    if len(odds_els) >= 2:
                        odds["home"] = odds_els[0].inner_text()
                        odds["away"] = odds_els[1].inner_text()
                    
                    matches.append({
                        "source": "flashscore",
                        "home_team": home.strip(),
                        "away_team": away.strip(),
                        "score": score.strip(),
                        "odds": odds,
                        "scraped_at": datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.debug(f"FlashScore match error: {e}")
                    
        except Exception as e:
            logger.error(f"FlashScore scrape error: {e}")
        finally:
            browser.close()
    
    return matches


def update_cricket_with_session_data(session_data: List[Dict]) -> int:
    """
    Update live_cricket table with session data.
    """
    if not session_data:
        return 0
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        updated = 0
        
        for data in session_data:
            teams_text = data.get("teams", data.get("match_name", ""))
            session_info = data.get("session_info", {})
            odds = data.get("odds", {})
            
            # Try to match by team name
            # Split teams
            if " vs " in teams_text.lower():
                parts = re.split(r'\s+vs?\s+', teams_text, flags=re.IGNORECASE)
            elif " v " in teams_text.lower():
                parts = re.split(r'\s+v\s+', teams_text, flags=re.IGNORECASE)
            else:
                parts = [teams_text]
            
            if len(parts) < 2:
                continue
                
            home = parts[0].strip()[:20]
            away = parts[1].strip()[:20]
            
            # Update with fuzzy match
            cur.execute("""
                UPDATE live_cricket
                SET 
                    other_odds = COALESCE(other_odds, '{}'::jsonb) || %s::jsonb,
                    last_updated = NOW()
                WHERE 
                    is_live = TRUE
                    AND (
                        (home_team ILIKE %s AND away_team ILIKE %s)
                        OR (home_team ILIKE %s AND away_team ILIKE %s)
                    )
                RETURNING match_id
            """, (
                Json({
                    "session": session_info,
                    "external_odds": odds,
                    "source": data.get("source", "unknown"),
                    "session_updated": datetime.now().isoformat()
                }),
                f"%{home}%", f"%{away}%",
                f"%{away}%", f"%{home}%"
            ))
            
            if cur.rowcount > 0:
                updated += cur.rowcount
                logger.info(f"Updated: {home} vs {away}")
        
        conn.commit()
        conn.close()
        
        return updated
        
    except Exception as e:
        logger.error(f"DB update error: {e}")
        return 0


def run_cricket_session_scraper():
    """
    Main function to scrape and update cricket session data.
    """
    logger.info("=" * 60)
    logger.info("CRICKET SESSION ODDS SCRAPER (Playwright)")
    logger.info("=" * 60)
    
    all_data = []
    
    # CricBuzz
    logger.info("\n--- CricBuzz ---")
    cb_data = scrape_cricbuzz_session_data(headless=True)
    all_data.extend(cb_data)
    logger.info(f"Got {len(cb_data)} matches from CricBuzz")
    
    # FlashScore
    logger.info("\n--- FlashScore ---")
    fs_data = scrape_flashscore_cricket_odds(headless=True)
    all_data.extend(fs_data)
    logger.info(f"Got {len(fs_data)} matches from FlashScore")
    
    if not all_data:
        logger.warning("No session data collected!")
        return
    
    logger.info(f"\nTotal: {len(all_data)} matches with session data")
    
    # Show summary
    for d in all_data[:5]:
        name = d.get("match_name") or f"{d.get('home_team', '?')} vs {d.get('away_team', '?')}"
        session = d.get("session_info", {})
        rr = session.get("run_rate", "N/A")
        logger.info(f"  {name}: RR={rr}")
    
    # Update database
    updated = update_cricket_with_session_data(all_data)
    logger.info(f"\n✅ Updated {updated} cricket matches with session data")
    
    return all_data


if __name__ == "__main__":
    run_cricket_session_scraper()
