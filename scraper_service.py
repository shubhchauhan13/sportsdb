import time
import json
import requests
import sys
import os
import psycopg2
from psycopg2.extras import Json
import os
import threading
from flask import Flask
from playwright.sync_api import sync_playwright

# --- Fake Web Server for Render Free Tier ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Scraper is Running!", 200

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Configuration ---
# Read from Environment Variable (Best for Replit/Production)
# Fallback to hardcoded string if env var not set
DB_CONNECTION_STRING = os.getenv(
    "DB_CONNECTION_STRING", 
    "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)
TARGET_API_URL = "https://api-v1.com/w/liveMatches2.php"

# Metadata Cache (Team Names, League Names)
TEAM_CACHE = {}     # ID -> Name
LEAGUE_CACHE = {}   # Match ID -> League Name
TIME_CACHE = {}     # Match ID -> Start Time (ms)


# --- Helper: Fetch Team Mappings ---
def scrape_mappings_from_url(page, url):
    """
    Scrapes a specific Crex URL to build ID -> Name mappings.
    """
    print(f"[CACHE] Scraping {url}...")
    try:
        page.goto(url, timeout=60000)
        time.sleep(5) # Wait for hydration
        
        # Scroll to load more
        for _ in range(3):
             page.mouse.wheel(0, 3000)
             time.sleep(1)
             
        # Extract Data via JSON in script tag (Robust Method)
        # The page contains a script tag with id="app-root-state" which has the full state
        
        matches_data = []
        try:
            # Get the script content
            script_content = page.locator("script#app-root-state").text_content(timeout=5000)
            
            if script_content:
                # Decode entities: &q; -> ", &s; -> ', &a; -> &
                clean_json = script_content.replace("&q;", '"').replace("&s;", "'").replace("&a;", "&")
                
                import json
                state_data = json.loads(clean_json)
                
                # The data structure usually has keys like "https://crickapi.com/fixture/getFixture"
                # We look for any list value that contains objects with 'matchFkey' or 'team1'
                
                for key, val in state_data.items():
                    if isinstance(val, list):
                        # check first item
                        if len(val) > 0 and isinstance(val[0], dict):
                            if "matchFkey" in val[0] or "mf" in val[0]:
                                matches_data.extend(val)
        except Exception as e:
            print(f"[WARN] Failed to extract JSON state: {e}")
            # Fallback to empty list or DOM scraping if needed, but this source is primary
            pass

        count = 0
        for item in matches_data:
            # Map fields
            # match_id -> mf (or matchFkey)
            # team_a_id -> t1f (or team1fkey)
            # team_b_id -> t2f (or team2fkey)
            # team_a_name -> team1
            # team_b_name -> team2
            # league -> seriesShortName or n
            # time -> t (timestamp)
            
            match_id = item.get("mf") or item.get("matchFkey")
            if not match_id:
                continue
                
            team_a_id = item.get("t1f") or item.get("team1fkey")
            team_b_id = item.get("t2f") or item.get("team2fkey")
            
            team_a_name = item.get("team1")
            team_b_name = item.get("team2")
            
            # Short names if needed
            # team_a_short = item.get("t1SName")
            
            # Update TEAM_CACHE
            if team_a_id and team_a_name and "Team " not in team_a_name:
                TEAM_CACHE[team_a_id] = team_a_name.strip()
            if team_b_id and team_b_name and "Team " not in team_b_name:
                TEAM_CACHE[team_b_id] = team_b_name.strip()
                
            # League Name
            league_name = item.get("seriesShortName") or item.get("n") or "Unknown League"
            if league_name:
                LEAGUE_CACHE[match_id] = league_name.strip()
                
            # Time
            timestamp = item.get("t")
            if timestamp:
                TIME_CACHE[match_id] = int(timestamp)
                
            count += 1
                    
        print(f"[CACHE] Extracted {count} matches from {url}")
        
    except Exception as e:
        print(f"[WARN] Failed to scrape {url}: {e}")

def run_periodic_cache_refresh():
    """
    Runs in a background thread to refresh mappings every 10 minutes.
    """
    print("[CACHE] Starting Background Cache Refresher...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
             user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
             viewport={"width": 1280, "height": 720}
        )
        
        while True:
            try:
                page = context.new_page()
                
                # 1. Scrape Live Scores (Critical for current matches)
                scrape_mappings_from_url(page, "https://crex.com/live-cricket-scores")
                
                # 2. Scrape Fixtures (For upcoming)
                scrape_mappings_from_url(page, "https://crex.com/fixtures/match-list")
                
                page.close()
                print(f"[CACHE] Update Complete. Teams: {len(TEAM_CACHE)}, Leagues: {len(LEAGUE_CACHE)}")
                
            except Exception as e:
                print(f"[CACHE] Refresh failed: {e}")
                
            # Sleep for 10 minutes
            time.sleep(600)
        
        browser.close()

# --- Database Setup ---
def initialize_db():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Create table if not exists with JSONB column
        # Using unlogged table for performance if persistence isn't critical, but standard is fine
        cur.execute("""
            CREATE TABLE IF NOT EXISTS live_matches (
                match_id TEXT PRIMARY KEY,
                match_data JSONB,
                last_updated TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS cleanstate (
                match_id TEXT PRIMARY KEY,
                title TEXT,
                league TEXT,
                team_a TEXT,
                team_b TEXT,
                batting_team TEXT,
                score TEXT,
                status TEXT, -- Live/Break/Finished
                innings TEXT,
                odds JSONB,
                session JSONB,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        print("[SUCCESS] Connected to NeonDB and verified schema.")
        return conn
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return None

# --- Data Transformation ---
def transform_match_data(match_id, raw):
    """
    Deciphers the cryptic Crex keys into readable JSON.
    """
    # Key Mapping (Reverse Engineered)
    # j -> score ("132/6(19.0)")
    # b -> team_a_short
    # c -> team_b_short
    # res -> status text
    # ti -> start_time (ms)
    
    status_text = raw.get("res", "") or "In Progress"
    
    # Heuristic for "Live": 
    # If it has a score ('j') AND isn't explicitly finished ('won by', 'tied', 'abandoned')
    # This is a basic check.
    is_finished = any(x in status_text.lower() for x in ["won by", "tied", "abandoned", "no result"])
    is_live = not is_finished
    
    # Enrich Team Names
    team_a_id = raw.get("b")
    team_b_id = raw.get("c")
    team_a_name = TEAM_CACHE.get(team_a_id, f"Team {team_a_id}")
    team_b_name = TEAM_CACHE.get(team_b_id, f"Team {team_b_id}")
    
    # Enrich Batting Team (New Logic)
    # Enrich Batting Team
    batting_indicator = raw.get("d", 0)
    try:
        batting_indicator = int(batting_indicator)
    except:
        batting_indicator = 0

    batting_team_id = None
    batting_team_name = None
    
    if batting_indicator == 1:
        batting_team_id = team_a_id
        batting_team_name = team_a_name
    elif batting_indicator == 2:
        batting_team_id = team_b_id
        batting_team_name = team_b_name
        
    # Enrich Status
    status_code = raw.get("a", "")
    match_status = "Unknown"
    
    if "^1" in status_code or "&1" in status_code or "^0" in status_code: 
        match_status = "Upcoming"
    elif "^2" in status_code: 
        match_status = "Live"
    elif "^3" in status_code: 
        match_status = "Completed"
        
    # League/Series Name
    league_name = LEAGUE_CACHE.get(match_id, raw.get("fo", "Unknown League")) 

    # Innings
    innings_code = raw.get("i", "0")
    try:
        innings_int = int(innings_code)
        if innings_int == 0: current_innings = "1st Innings"
        elif innings_int == 1: current_innings = "2nd Innings"
        elif innings_int == 2: current_innings = "3rd Innings"
        elif innings_int == 3: current_innings = "4th Innings"
        else: current_innings = f"{innings_int + 1}th Innings"
    except:
        current_innings = "1st Innings"

    raw_score_a = raw.get("j", "")
    raw_score_b = raw.get("k", "")
    
    # Clean scores (remove brackets if needed, but usually we want specific formats)
    # Keeping raw strings for now
    
    score = raw_score_a # Default fallback
    
    if batting_indicator == 2:
        # Team B is batting
        if raw_score_b:
            score = raw_score_b
        elif raw_score_a:
            score = raw_score_a # Fallback to A if B missing
    elif batting_indicator == 1:
        # Team A is batting
        if raw_score_a:
            score = raw_score_a
        elif raw_score_b:
            score = raw_score_b # Fallback
    else:
        # Unknown batting team
        if raw_score_a and raw_score_b:
             score = f"{raw_score_a} vs {raw_score_b}"
        else:
             score = raw_score_a or raw_score_b

    # Add Target Logic (If 2nd Innings)
    target = ""
    if current_innings == "2nd Innings":
         # If B is batting, target is A's score
         if batting_indicator == 2: target = raw_score_a
         elif batting_indicator == 1: target = raw_score_b

    # Handle & splits if they still happen in individual fields
    if score and "&" in score:
         score = score.split('&')[-1].strip()



    
    # Granular Event State
    event_state = "Live"
    lower_res = status_text.lower()
    
    if "won by" in lower_res or "tied" in lower_res or "no result" in lower_res or match_status == "Completed":
        event_state = "Finished"
    elif "break" in lower_res or "delay" in lower_res or "stumps" in lower_res:
         event_state = "Break"
    elif match_status == "Upcoming":
         event_state = "Scheduled"
         
    # Fallback: If status is unknown but we know it's finished, set status to Completed
    if match_status == "Unknown" and event_state == "Finished":
        match_status = "Completed"
         
    # Fix is_live based on event_state
    is_live = (event_state == "Live" or event_state == "Break") and event_state != "Finished"
    
    # Enrich Timestamp
    start_timestamp = raw.get("ti", 0)
    
    # Fix: Use Time Cache if available and timestamp is 0 or invalid
    if (not start_timestamp or start_timestamp == 0) and match_id in TIME_CACHE:
        start_timestamp = TIME_CACHE[match_id]
        
    start_time_iso = ""
    try:
        if start_timestamp:
             # ti is ms. Convert to UTC ISO explicitly
             start_time_iso = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(start_timestamp)/1000))
    except:
        pass
        
    # --- ODDS GENERATION ---
    mm_odds = {}
    wp_str = raw.get("wp") # e.g. "M2,9085,19261,0" or "O,339401,143702,0"
    
    if wp_str and isinstance(wp_str, str):
        try:
            parts = wp_str.split(',')
            if len(parts) >= 3:
                fav_id = parts[0]
                val1 = int(parts[1])
                val2 = int(parts[2])
                total = val1 + val2
                
                if total > 0:
                    prob_fav = val1 / total
                    prob_under = val2 / total
                    
                    # Decimal Odds = 1 / Probability
                    # Add a 5% margin? No, keep raw fair odds for now.
                    odds_fav = round(1 / prob_fav, 2)
                    odds_under = round(1 / prob_under, 2)
                    
                    # Map to Team A / Team B
                    if team_a_id == fav_id:
                        mm_odds = {
                            "team_a_win_prob": round(prob_fav * 100, 1),
                            "team_b_win_prob": round(prob_under * 100, 1),
                            "team_a_odds": odds_fav,
                            "team_b_odds": odds_under
                        }
                    else:
                        mm_odds = {
                            "team_a_win_prob": round(prob_under * 100, 1),
                            "team_b_win_prob": round(prob_fav * 100, 1),
                            "team_a_odds": odds_under,
                            "team_b_odds": odds_fav
                        }
        except Exception as e:
            # print(f"Odds Error: {e}")
            pass

    # --- SESSION / PROJECTION ---
    session_data = {}
    score_str = raw.get("j") # "19/3(5.2)"
    if score_str and "(" in score_str and is_live:
        try:
            # Basic CRR Scraper
            # Format: Runs/Wickets (Overs) or Runs-Wickets (Overs)
            main_part, over_part = score_str.split('(')
            runs = 0
            wickets = 0
            
            if "/" in main_part:
                r, w = main_part.split('/')
                runs = int(r)
                wickets = int(w)
            elif "-" in main_part:
                r, w = main_part.split('-')
                runs = int(r)
                wickets = int(w)
            else:
                runs = int(main_part)
            
            overs_float = float(over_part.replace(')', ''))
            
            # Helper to convert 5.2 to 5.333
            ov_int = int(overs_float)
            balls = int(round((overs_float - ov_int) * 10))
            real_overs = ov_int + (balls / 6.0)
            
            if real_overs > 0:
                crr = runs / real_overs
                
                # Determine Format (T20 vs ODI)
                total_overs = 20
                if "ODI" in raw.get("fo", ""): total_overs = 50
                if "Test" in raw.get("fo", ""): total_overs = 90 # Per day approx
                
                # Basic Projection: Current Rate * Total Overs
                proj_score_crr = int(crr * total_overs)
                
                # Smart Projection (Wicket Adjusted)
                # If wickets high, reduce rate
                # Simplistic model: CRR * (1 - (wickets/15)) -> Decay factor
                
                session_data = {
                    "runs": runs,
                    "wickets": wickets,
                    "overs": real_overs,
                    "crr": round(crr, 2),
                    "projected_score": proj_score_crr,
                    "session_6_over_guess": int(runs + (crr * (6 - real_overs))) if real_overs < 6 else None
                }
        except:
            pass

    return {
        "match_id": match_id,
        "is_live": is_live,

        "match_id": match_id,
        "is_live": is_live,
        "match_status": match_status, 
        "event_state": event_state,           # [NEW] "Live", "Break", "Finished"
        "status_text": status_text,   
        "score": score,
        "team_a_score": raw_score_a,          # [NEW]
        "team_b_score": raw_score_b,          # [NEW]
        "target": target,                     # [NEW]
        "team_a": team_a_id,
        "team_b": team_b_id,
        "team_a_name": team_a_name,
        "team_b_name": team_b_name,
        "batting_team": batting_team_id,      
        "batting_team_name": batting_team_name, 
        "current_innings": current_innings,   # [NEW]
        "league_name": league_name,           # [NEW]
        "match_odds": mm_odds,                # [NEW]
        "session": session_data,              # [NEW]
        "format": raw.get("fo"),
        "start_time": start_timestamp,
        "start_time_iso": start_time_iso,
        "title": f"{team_a_name} vs {team_b_name}",
        "raw": raw # Keep raw data for backup
    }

# --- Data Processing ---
def process_and_upload(conn, data):
    """
    Upserts match data into NeonDB.
    """
    if not isinstance(data, dict):
        return

    match_count = 0
    live_count = 0
    
    try:
        cur = conn.cursor()
        
        for match_id, match_info in data.items():
            if isinstance(match_info, dict):
                # Transform data
                clean_data = transform_match_data(match_id, match_info)
                if clean_data["is_live"]:
                    live_count += 1
                
                # UPSERT
                cur.execute("""
                    INSERT INTO live_matches (match_id, match_data, last_updated)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (match_id) 
                    DO UPDATE SET match_data = EXCLUDED.match_data, last_updated = NOW();
                """, (match_id, Json(clean_data)))
                
                # UPSERT into cleanstate
                cur.execute("""
                    INSERT INTO cleanstate (
                        match_id, title, league, team_a, team_b, batting_team, 
                        score, status, innings, odds, session, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (match_id)
                    DO UPDATE SET 
                        title = EXCLUDED.title,
                        league = EXCLUDED.league,
                        team_a = EXCLUDED.team_a,
                        team_b = EXCLUDED.team_b,
                        batting_team = EXCLUDED.batting_team,
                        score = EXCLUDED.score,
                        status = EXCLUDED.status,
                        innings = EXCLUDED.innings,
                        odds = EXCLUDED.odds,
                        session = EXCLUDED.session,
                        updated_at = NOW();
                """, (
                    match_id, 
                    clean_data.get("title"),
                    clean_data.get("league_name"),
                    clean_data.get("team_a_name"),
                    clean_data.get("team_b_name"),
                    clean_data.get("batting_team_name"),
                    clean_data.get("score"),
                    clean_data.get("event_state"),
                    clean_data.get("current_innings"),
                    Json(clean_data.get("match_odds")),
                    Json(clean_data.get("session"))
                ))

                
                match_count += 1
        
        conn.commit()
        if match_count > 0:
            print(f"[SYNC] Upserted {match_count} matches (Live: {live_count}).")

            
    except Exception as e:
        print(f"[SYNC ERROR] {e}")
        conn.rollback() # Important to rollback on error to keep connection healthy

# --- Main Polling Loop ---
def run_scraper():
    conn = initialize_db()
    if not conn:
        print("Exiting due to DB failure.")
        return

    print("Starting Active Polling Scraper for NeonDB...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Context mimics browser behavior
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            base_url="https://api-v1.com",
            extra_http_headers={
                "Origin": "https://crex.com",
                "Referer": "https://crex.com/"
            }
        )
        
        
        # Initial scraping is now handled by the background thread.
        # Check if we need to wait a bit for the first cache population?
        print("Waiting for initial cache population...")
        time.sleep(10) 
        
        
        try:
            while True:
                start_time = time.time()
                try:
                    # Active Poll
                    response = context.request.post(TARGET_API_URL)
                    
                    if response.ok:
                        try:
                            data = response.json()
                            process_and_upload(conn, data)
                        except:
                            print("[WARN] Invalid JSON response")
                    else:
                        print(f"[WARN] API Error: {response.status}")
                        
                except Exception as e:
                    print(f"[ERROR] Polling failed: {e}")
                    # Try to reconnect if connection dropped
                    if conn.closed:
                         print("Reconnecting to DB...")
                         conn = initialize_db()
                
                # Goal: 1 second interval
                # Calculate sleep time to account for network latency
                elapsed = time.time() - start_time
                sleep_time = max(0.01, 1.0 - elapsed)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("Stopping scraper...")
        finally:
            if conn: conn.close()
            browser.close()

if __name__ == "__main__":
    # Start Web Server in Background Thread
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    print("background web server started")
    
    # Run Main Scraper Loop
    
    # Start Cache Thread
    cache_thread = threading.Thread(target=run_periodic_cache_refresh, daemon=True)
    cache_thread.start()
    
    run_scraper()
