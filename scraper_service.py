import time
import json
import os
import psycopg2
from psycopg2.extras import Json
import threading
from flask import Flask
from playwright.sync_api import sync_playwright
import traceback

# --- Fake Web Server for Render Free Tier ---
app = Flask(__name__)

@app.route('/')
def home():
    return "SofaScore Scraper Running (8 Sports)..."

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Configuration ---
DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING", 
    "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
).strip("'").strip('"')

# Sport Configuration
SPORTS_CONFIG = {
    'cricket':       {'slug': 'cricket',       'table': 'live_cricket',      'has_draw': True},
    'football':      {'slug': 'football',      'table': 'live_football',     'has_draw': True},
    'tennis':        {'slug': 'tennis',        'table': 'live_tennis',       'has_draw': False},
    'basketball':    {'slug': 'basketball',    'table': 'live_basketball',   'has_draw': False}, # OT usually included
    'table-tennis':  {'slug': 'table-tennis',  'table': 'live_table_tennis', 'has_draw': False},
    'ice-hockey':    {'slug': 'ice-hockey',    'table': 'live_ice_hockey',   'has_draw': True}, # 3-way markets exist
    'esports':       {'slug': 'esports',       'table': 'live_esports',      'has_draw': False},
    'motorsport':    {'slug': 'motorsport',    'table': 'live_motorsport',   'has_draw': False} 
}

# --- Database Setup ---
def initialize_db():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        for sport, config in SPORTS_CONFIG.items():
            table = config['table']
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
                    home_odds TEXT,
                    away_odds TEXT,
                    draw_odds TEXT,
                    last_updated TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Auto-Migration for new columns using separate transactions to avoid blocks
            columns = [
                ('batting_team', 'TEXT'),
                ('is_live', 'BOOLEAN DEFAULT FALSE'),
                ('home_score', 'TEXT'),
                ('away_score', 'TEXT'),
                ('home_odds', 'TEXT'),
                ('away_odds', 'TEXT'),
                ('draw_odds', 'TEXT')
            ]
            for col_name, col_type in columns:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};")
                    conn.commit()
                except Exception: 
                    conn.rollback()
            
        conn.commit()
        print("[SUCCESS] Connected to NeonDB and verified schemas.")
        return conn
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return None

# --- Formatting Helpers ---

def format_score(sport, score_obj):
    """
    Generic score formatter based on sport.
    """
    if not score_obj: return "0"
    
    display = str(score_obj.get('display', 0))
    
    if sport == 'cricket':
        # "250/3 (45.2)"
        innings = score_obj.get('innings', {})
        if innings:
            runs = display
            wickets = 0
            overs = 0.0
            # Sum up/Latest logic (simplified)
            for _, val in innings.items():
                if 'score' in val: runs = val.get('score', runs)
                wickets = val.get('wickets', 0)
                overs = val.get('overs', 0.0)
            return f"{runs}/{wickets} ({overs})"
        return display

    elif sport == 'tennis':
        return display # Sets
        
    elif sport == 'basketball':
        return display # Points
        
    elif sport == 'table-tennis':
        return display # Sets
        
    elif sport == 'ice-hockey':
        return display # Goals
        
    elif sport == 'esports':
        return display # Maps/Rounds

    return display


def construct_score_string(sport, h_fmt, a_fmt):
    if h_fmt == "0" and a_fmt == "0":
        return "vs"
        
    if sport == 'cricket':
        return f"{h_fmt} vs {a_fmt}"
    elif sport == 'tennis' or sport == 'table-tennis':
        return f"{h_fmt} - {a_fmt} (Sets)"
    elif sport == 'esports':
        return f"{h_fmt} - {a_fmt} (Maps)"
    
    return f"{h_fmt} - {a_fmt}"

# --- Odds Fetching ---

def fetch_odds(page, event_id):
    """
    Fetches real odds for a match from SofaScore.
    Returns: { 'home': '1.5', 'away': '2.5', 'draw': '3.4' }
    """
    url = f"https://www.sofascore.com/api/v1/event/{event_id}/odds/1/all"
    odds_data = {'home': None, 'away': None, 'draw': None}
    
    try:
        # Check if page is closed
        if page.is_closed(): return odds_data
        
        # Navigation with short timeout
        response = page.goto(url, timeout=3000)
        if not response or response.status != 200:
            return odds_data
            
        text = page.inner_text("body")
        data = json.loads(text)
        
        # Look for "Full time" market (marketId 1)
        markets = data.get('markets', [])
        full_time = next((m for m in markets if m.get('marketId') == 1), None)
        
        if full_time:
            choices = full_time.get('choices', [])
            for c in choices:
                name = c.get('name')
                fractional = c.get('fractionalValue')
                
                # Simple decimal conversion if possible, else keep fractional
                val = fractional
                try:
                    if '/' in fractional:
                        num, den = map(int, fractional.split('/'))
                        dec = 1 + (num / den)
                        val = f"{dec:.2f}"
                except: pass
                
                if name == '1': odds_data['home'] = val
                elif name == '2': odds_data['away'] = val
                elif name == 'X': odds_data['draw'] = val
                
    except Exception:
        pass
        
    return odds_data

# --- Main Scraper Logic ---

def fetch_sofascore_live(page, sport_slug):
    ts = int(time.time() * 1000)
    url = f"https://www.sofascore.com/api/v1/sport/{sport_slug}/events/live?_={ts}"
    events = []
    try:
        if page.is_closed(): return []
        response = page.goto(url, timeout=15000)
        if response and response.status == 200:
            text = page.inner_text("body")
            data = json.loads(text)
            events = data.get('events', [])
    except Exception as e:
        print(f"[WARN] Fetch {sport_slug} failed: {e}")
    return events

def upsert_matches(conn, sport_key, matches, page):
    if not matches: return []
    
    ids = []
    config = SPORTS_CONFIG[sport_key]
    table_name = config['table']
    has_draw = config['has_draw']
    
    try:
        cur = conn.cursor()
        count = 0
        
        for m in matches:
            match_id = str(m.get('id'))
            ids.append(match_id)
            
            # Basic Info
            home_team = m.get('homeTeam', {}).get('name', 'Unknown')
            away_team = m.get('awayTeam', {}).get('name', 'Unknown')
            status = m.get('status', {}).get('description', 'Unknown')
            
            # Formatted Scores
            h_fmt = format_score(sport_key, m.get('homeScore', {}))
            a_fmt = format_score(sport_key, m.get('awayScore', {}))
            score_str = construct_score_string(sport_key, h_fmt, a_fmt)
            
            # Batting Team (Cricket)
            batting_team = None
            if sport_key == 'cricket' and m.get('currentBattingTeamId'):
                bid = m.get('currentBattingTeamId')
                if bid == m.get('homeTeam', {}).get('id'): batting_team = home_team
                elif bid == m.get('awayTeam', {}).get('id'): batting_team = away_team
            
            # Fetch Real Odds with slight delay to avoid blocks
            odds = fetch_odds(page, match_id)
            time.sleep(0.1) 
            
            # Fallback Simulation (If no odds found)
            if not odds['home'] and not odds['away']:
                # Placeholders
                odds['home'] = "1.90"
                odds['away'] = "1.90"
                if has_draw: odds['draw'] = "3.50"
            
            cur.execute(f"""
                INSERT INTO {table_name} (
                    match_id, match_data, home_team, away_team, status, score, 
                    batting_team, is_live, home_score, away_score, 
                    home_odds, away_odds, draw_odds, last_updated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
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
                    home_odds = EXCLUDED.home_odds,
                    away_odds = EXCLUDED.away_odds,
                    draw_odds = EXCLUDED.draw_odds,
                    last_updated = NOW();
            """, (
                match_id, Json(m), home_team, away_team, status, score_str, 
                batting_team, True, h_fmt, a_fmt, 
                odds['home'], odds['away'], odds.get('draw')
            ))
            
            count += 1
            
        conn.commit()
        if count > 0:
            print(f"[SYNC] {sport_key}: Upserted {count} matches.")
            
    except Exception as e:
        print(f"[DB ERROR] {sport_key}: {e}")
        conn.rollback()
        
    return ids

# --- Supervisor ---

def run_scraper():
    while True:
        print("\n[SUPERVISOR] Starting Scraper...")
        conn = None
        browser = None
        
        try:
            conn = initialize_db()
            if not conn:
                time.sleep(10)
                continue

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                cycle_count = 0
                while True:
                    start_time = time.time()
                    
                    for sport, config in SPORTS_CONFIG.items():
                        try:
                            # DB Check
                            if conn.closed: raise Exception("DB Conn Closed")

                            matches = fetch_sofascore_live(page, config['slug'])
                            if matches:
                                upsert_matches(conn, sport, matches, page)
                            
                        except Exception as e:
                            print(f"[ERROR] {sport}: {e}")
                            if "closed" in str(e).lower() or "connection" in str(e).lower():
                                raise e
                    
                    elapsed = time.time() - start_time
                    # 15s to 30s cycle to be polite with odds fetching
                    time.sleep(max(10.0, 30.0 - elapsed)) 
                    
                    cycle_count += 1
                    if cycle_count >= 20: 
                        print("[SUPERVISOR] Scheduled Restart...")
                        break

        except Exception as e:
            print(f"[CRASH] {e}")
            time.sleep(10)
        finally:
            try: 
                if browser: browser.close()
            except: pass
            try: 
                if conn: conn.close()
            except: pass

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    run_scraper()
