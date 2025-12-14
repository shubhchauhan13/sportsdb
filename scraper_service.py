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

# Team Mapping Cache (In-Memory)
TEAM_CACHE = {}

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
                id_a = parts[5] # 1DY
                id_b = parts[6] # 1DZ
                
                # Get text content of the card to find names
                text = link.inner_text()
                # Split by newline or common separators
                # The names typically appear distinctly. 
                # e.g. "Sierra Leone\n132/6\nvs\nZambia..."
                # We can just store the IDs for now if text parsing is hard, 
                # but let's try to grab specific elements if angular allows.
                
                # Simple fallback: ID -> ID (Better than nothing)
                # But we want names.
                # Let's trust that the user might have a static list or we assume the first two distinct capitalized words are names?
                # Too risky.
                
                # For this specific task, let's look for .team-name class inside the link?
                try:
                    names = link.locator(".team-name, .t-name").all_inner_texts()
                    if len(names) >= 2:
                        TEAM_CACHE[id_a] = names[0]
                        TEAM_CACHE[id_b] = names[1]
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
    team_b_name = TEAM_CACHE.get(team_b_id, f"Team {team_b_id}")
    
    # Enrich Status
    # ^1=Upcoming, ^2=Live, ^3=Completed (User provided)
    status_code = raw.get("a", "")
    match_status = "Unknown"
    if "^1" in status_code: match_status = "Upcoming"
    elif "^2" in status_code: match_status = "Live"
    elif "^3" in status_code: match_status = "Completed"
    
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
        "match_status": match_status, # Parsed from 'a'
        "status_text": status_text,   # Parsed from 'res'
        "score": raw.get("j"),
        "team_a": team_a_id,
        "team_b": team_b_id,
        "team_a_name": team_a_name,
        "team_b_name": team_b_name,
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
