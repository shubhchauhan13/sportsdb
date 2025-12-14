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


# --- Helper: Fetch Team Mappings ---
def fetch_team_mappings(page):
    """
    Scrapes the fixtures page to build a ID -> Name mapping.
    """
    print("[INIT] Fetching team mappings from Fixtures page...")
    try:
        page.goto("https://crex.com/fixtures/match-list", timeout=30000)
        time.sleep(3)
        
        # Select all match card links
        # URL pattern: /scoreboard/MATCH_ID/SERIES_ID/STAGE/TEAM_A_ID/TEAM_B_ID/SLUG
        # We need to extract TEAM_A_ID and TEAM_B_ID and correlate with visible text
        
        # This is a bit "fuzzy" because text order vs url ID order usually matches (Home vs Away)
        # We'll use a safer heuristic if possible, but for now assuming strict order.
        
        # Let's grab all links with 'scoreboard'
        links = page.locator("a[href*='/scoreboard/']").all()
        
        count = 0
        for link in links:
            href = link.get_attribute("href")
            # Example: /scoreboard/YCY/246/3rd-Place-Playoff/1DY/1DZ/sil-vs-zam-...
            parts = href.split('/')
            if len(parts) >= 7:
                id_b = parts[6] # 1DZ
                match_id = parts[4] if len(parts) > 4 else None # Extract Match ID from URL if possible?
                # Actually, URL is /scoreboard/MATCH_ID/SERIES_ID/...
                # Example: /scoreboard/YCY/246/...
                potential_match_id = parts[2]
                
                # Get text content
                # Try to get League Name (Card usually has a header or label)
                # But on match-list, headers are separate.
                # Heuristic: We can't easily get the header for each item without complex traversal.
                # However, usually the card itself has text like "T20I . 3rd Place Playoff"
                # Let's try to grab the card text and assume the first line is Series/League info if needed.
                
                # For now, let's focus on names as before.
                try:
                     names = link.locator(".team-name, .t-name").all_inner_texts()
                     if len(names) >= 2:
                         TEAM_CACHE[id_a] = names[0]
                         TEAM_CACHE[id_b] = names[1]
                         
                     # Try to find League/Series info in the card
                     # Often in a .series-name or .match-info div
                     series_info = link.locator(".series-name, .match-info, .card-header").first.inner_text()
                     if series_info and potential_match_id:
                         LEAGUE_CACHE[potential_match_id] = series_info
                         
                     count += 1
                except:
                     pass

        print(f"[INIT] Cached {len(TEAM_CACHE)} team names.")
        
    except Exception as e:
        print(f"[WARN] Failed to fetch mappings: {e}")

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
    team_a_name = TEAM_CACHE.get(team_a_id, f"Team {team_a_id}")
    team_b_name = TEAM_CACHE.get(team_b_id, f"Team {team_b_id}")
    
    # Enrich Batting Team (New Logic)
    # d=1 -> Team A (Home) is batting
    # d=2 -> Team B (Away) is batting
    batting_indicator = raw.get("d", 0)
    batting_team_id = None
    batting_team_name = None
    
    if batting_indicator == 1:
        batting_team_id = team_a_id
        batting_team_name = team_a_name
    elif batting_indicator == 2:
        batting_team_id = team_b_id
        batting_team_name = team_b_name
        
    # Enrich Status
    # ^1=Upcoming, ^2=Live, ^3=Completed/In-Play (Context dependent)
    # Start with explicit match_status from 'res' if matches specific keywords

    # ^1, &1, ^0... usually mean upcoming or pre-match
    # ^2 = Live
    # ^3 = Completed
    status_code = raw.get("a", "")
    match_status = "Unknown"
    
    if "^1" in status_code or "&1" in status_code or "^0" in status_code: 
        match_status = "Upcoming"
    elif "^2" in status_code: 
        match_status = "Live"
    elif "^3" in status_code: 
        match_status = "Completed"
        
    # League/Series Name
    league_name = LEAGUE_CACHE.get(match_id, raw.get("fo", "Unknown League")) # Fallback to format if league not found

    # Innings
    # i=1 -> 1st Innings, i=2 -> 2nd Innings, i=3 -> 3rd Innings (Test), etc.
    innings = raw.get("i", 0)
    current_innings = f"{innings}th Innings" if innings else "Not Started"
    if innings == 1: current_innings = "1st Innings"
    elif innings == 2: current_innings = "2nd Innings"

    
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
    start_time_iso = ""
    try:
        if start_timestamp:
             # ti is usually ms
             start_time_iso = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(start_timestamp)/1000))
    except:
        pass

    return {
        "match_id": match_id,
        "is_live": is_live,
        "match_status": match_status, 
        "event_state": event_state,           # [NEW] "Live", "Break", "Finished"
        "status_text": status_text,   
        "score": raw.get("j"),
        "team_a": team_a_id,
        "team_b": team_b_id,
        "team_a_name": team_a_name,
        "team_b_name": team_b_name,
        "batting_team": batting_team_id,      
        "batting_team_name": batting_team_name, 
        "current_innings": current_innings,   # [NEW]
        "league_name": league_name,           # [NEW]
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
        
        # Initial scraping of team names
        try:
             page_map = context.new_page()
             fetch_team_mappings(page_map)
             page_map.close()
        except Exception as e:
             print(f"Skipping map fetch: {e}")
        
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
    run_scraper()
