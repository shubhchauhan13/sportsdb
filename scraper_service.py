import time
import json
import os
import psycopg2
from psycopg2.extras import Json
import threading
from flask import Flask
from playwright.sync_api import sync_playwright

# --- Fake Web Server for Render Free Tier ---
app = Flask(__name__)

@app.route('/')
def home():
    return "SofaScore Scraper Running..."

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Configuration ---
DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING", 
    "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# --- Database Setup ---
def initialize_db():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Create Tables for Each Sport
        # We start with cricket as requested, but structure allows others
        sports = ['live_cricket', 'live_football', 'live_tennis']
        

        # Create Tables for Each Sport
        sports = ['live_cricket', 'live_football', 'live_tennis']
        
        for table in sports:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    match_id TEXT PRIMARY KEY,
                    match_data JSONB,
                    home_team TEXT,
                    away_team TEXT,
                    status TEXT,
                    score TEXT,
                    batting_team TEXT,
                    is_live BOOLEAN DEFAULT FALSE,
                    home_score TEXT,
                    away_score TEXT,
                    last_updated TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Auto-Migration for new columns (safe per table)
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN batting_team TEXT;")
            except Exception: conn.rollback()
                
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN is_live BOOLEAN DEFAULT FALSE;")
            except Exception: conn.rollback()
            
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN home_score TEXT;")
            except Exception: conn.rollback()

            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN away_score TEXT;")
            except Exception: conn.rollback()

        conn.commit()
        print("[SUCCESS] Connected to NeonDB and verified schemas.")
        return conn
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return None

# --- SofaScore Scraper ---

def fetch_sofascore_live(page, sport_slug="cricket"):
    """
    Fetches live events for a specific sport from SofaScore API via direct navigation.
    We iterate through a few known API endpoints to ensure coverage.
    """
    # Cache-busting: Add timestamp to force fresh data
    ts = int(time.time())
    
    # Try the clean API first which lists all live events for the sport
    urls = [
        f"https://www.sofascore.com/api/v1/sport/{sport_slug}/events/live?_={ts}",
    ]
    
    events = []
    
    for url in urls:
        try:
            # print(f"[*] Fetching {url}...")
            response = page.goto(url, timeout=30000)
            if response.status == 200:
                # The browser renders the JSON as text in the body
                text = page.inner_text("body")
                try:
                    data = json.loads(text)
                    batch = data.get('events', [])
                    events.extend(batch)
                except json.JSONDecodeError:
                    print(f"[WARN] Failed to parse JSON from {url}")
            else:
                print(f"[WARN] API Fetch Failed: {url} -> {response.status}")
                
        except Exception as e:
            print(f"[ERROR] Fetching {url}: {e}")
            
    return events


def format_cricket_score(score_data):
    """
    Parses SofaScore score object to return a standard cricket string: "Runs/Wickets (Overs)"
    Example: 150/3 (18.2)
    """
    if not score_data:
        return ""
        
    try:
        # 1. Try to get details from innings
        innings = score_data.get('innings', {})
        if innings:
            # Simple approach: find the latest inning populated
            runs = score_data.get('display', 0)
            wickets = 0
            overs = 0.0
            
            for key, val in innings.items():
                wickets += val.get('wickets', 0)
                if 'score' in val:
                     runs = val.get('score', runs)
                     wickets = val.get('wickets', 0)
                     overs = val.get('overs', 0.0)

            return f"{runs}/{wickets} ({overs})"
        
        # Fallback to simple runs
        return str(score_data.get('display', 0))
    except:
        return str(score_data.get('display', 0))


def format_football_score(score_data):
    """
    Football: HomeGoals - AwayGoals
    """
    if not score_data: return "0"
    return str(score_data.get('display', 0))

def format_tennis_score(score_data, periods=None):
    """
    Tennis: Sets (Game Scores)
    Example: 2 (6-4, 6-3)
    """
    if not score_data: return "0"
    sets = str(score_data.get('display', 0))
    
    # If raw period scores are available (games per set)
    # This is complex as it requires merging home/away periods. 
    # For now, just return Sets count.
    # To do it properly: We need the match object, not just one score object.
    # So we'll handle detailed string construction in the caller.
    return sets

def upsert_matches(conn, table_name, matches):
    if not matches:
        return
        
    try:
        cur = conn.cursor()
        count = 0
        ids = []
        
        sport = table_name.replace('live_', '')
        
        for m in matches:
            match_id = str(m.get('id'))
            ids.append(match_id)
            
            home_team = m.get('homeTeam', {}).get('name', 'Unknown')
            away_team = m.get('awayTeam', {}).get('name', 'Unknown')
            
            # Status Logic
            status_desc = m.get('status', {}).get('description', 'Unknown')
            last_period = m.get('lastPeriod')
            periods = m.get('periods', {})
            
            # Use period mapping if available (works for Cricket Innings, Tennis Sets)
            if last_period and last_period in periods:
                status = periods[last_period]
            else:
                status = status_desc
                
            status_type = m.get('status', {}).get('type', 'unknown')
            
            # Score Formatting based on Sport
            h_fmt = "0"
            a_fmt = "0"
            score_str = "vs"
            
            if sport == 'cricket':
                h_fmt = format_cricket_score(m.get('homeScore', {}))
                a_fmt = format_cricket_score(m.get('awayScore', {}))
                
                # Heuristic Fix for Cricket 2nd Innings
                try:
                    h_runs = int(m.get('homeScore', {}).get('display', 0))
                    a_runs = int(m.get('awayScore', {}).get('display', 0))
                    if h_runs > 0 and a_runs > 0 and "1st Inning" in status:
                        status = "2nd Inning"
                except: pass
                
            elif sport == 'football':
                h_fmt = format_football_score(m.get('homeScore', {}))
                a_fmt = format_football_score(m.get('awayScore', {}))
                
            elif sport == 'tennis':
                # Tennis: Display Sets. 
                # Ideally: "Sets (Games)"
                # m['homeScore']['period1'] = 6 etc.
                h_sets = m.get('homeScore', {}).get('display', 0)
                a_sets = m.get('awayScore', {}).get('display', 0)
                h_fmt = str(h_sets)
                a_fmt = str(a_sets)
                
                # Construct games string? "6-4, 2-1" etc
                # periods: { "point": "15", "period1": "6" ... } 
                # This is tricky without unified period list.
                # Just separate scores for now.
                
            # Construct Score String
            if h_fmt == "0" and a_fmt == "0":
                score_str = "vs"
            elif h_fmt and a_fmt:
                score_str = f"{h_fmt} - {a_fmt}"
                if sport == 'cricket':
                    score_str = f"{h_fmt} vs {a_fmt}"
            else:
                score_str = f"{h_fmt} {a_fmt}".strip()

            
            # Determine Batting Team (Cricket Only)
            batting_team_id = m.get('currentBattingTeamId')
            batting_team = None
            if sport == 'cricket' and batting_team_id:
                if batting_team_id == m.get('homeTeam', {}).get('id'):
                    batting_team = home_team
                elif batting_team_id == m.get('awayTeam', {}).get('id'):
                    batting_team = away_team
            
            # Is Live Check
            is_live = True
            if status_type == 'finished' or 'ended' in status.lower():
                is_live = False
            

            # 1. Upsert to Sport Specific Table
            cur.execute(f"""
                    INSERT INTO {table_name} (
                        match_id, match_data, home_team, away_team, status, score, 
                        batting_team, is_live, home_score, away_score, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (match_id) DO UPDATE SET
                        match_data = EXCLUDED.match_data,
                        home_team = EXCLUDED.home_team,
                        away_team = EXCLUDED.away_team,
                        status = EXCLUDED.status,
                        score = EXCLUDED.score,
                        batting_team = EXCLUDED.batting_team,
                        is_live = EXCLUDED.is_live,
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        last_updated = NOW();
                """, (match_id, Json(m), home_team, away_team, status, score_str, batting_team, is_live, h_fmt, a_fmt))
                
            count += 1

            
        conn.commit()
        if count > 0:
            print(f"[SYNC] Upserted {count} matches to {table_name}.")
    except Exception as e:
        print(f"[DB ERROR] {e}")
        conn.rollback()


def run_scraper():
    conn = initialize_db()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Starting SofaScore Polling for Cricket, Football, Tennis...")
        
        try:
            while True:
                start_time = time.time()
                
                # Cycle through sports
                sports_config = [
                    ('cricket', 'live_cricket'),
                    ('football', 'live_football'),
                    ('tennis', 'live_tennis')
                ]
                
                for sport_slug, table_name in sports_config:
                    try:
                        if conn and conn.closed:
                            print(f"[{sport_slug}] Reconnecting to DB...")
                            conn = initialize_db()
                            if not conn:
                                print(f"[{sport_slug}] Failed to reconnect to DB. Skipping {sport_slug}.")
                                continue
                        
                        matches = fetch_sofascore_live(page, sport_slug)
                        if conn:
                            upsert_matches(conn, table_name, matches)
                        else:
                            print(f"[{sport_slug}] DB connection not available. Skipping upsert for {sport_slug}.")
                        time.sleep(2) # Short pause between sports
                    except Exception as e:
                        print(f"[{sport_slug}] Error: {e}")
                
                elapsed = time.time() - start_time
                sleep_time = max(2.0, 5.0 - elapsed)
                time.sleep(sleep_time) # Wait before next cycle, ensuring at least 5s total per cycle
                
        except KeyboardInterrupt:
            print("Stopping Scraper...")
        finally:
            browser.close()
            if conn:
                conn.close()

if __name__ == "__main__":
    # Start Web Server in Background Thread
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    
    run_scraper()
