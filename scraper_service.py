import time
import json
import os
import psycopg2
from psycopg2.extras import Json
import threading
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
import traceback
import collections
from datetime import datetime

# --- Global State for Diagnostics ---
SCRAPER_STATS = {
    'started_at': str(datetime.now()),
    'sports': {},
    'last_error': None
}
LOG_BUFFER = collections.deque(maxlen=100)

def log_msg(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    LOG_BUFFER.append(entry)

# --- Fake Web Server for Render Free Tier ---
app = Flask(__name__)

@app.route('/')
def home():
    return f"AiScore Scraper Running... Last Error: {SCRAPER_STATS.get('last_error')}"

@app.route('/health')
def health():
    return jsonify({
        "status": "running",
        "stats": SCRAPER_STATS,
        "logs_tail": list(LOG_BUFFER)[-5:]
    })

@app.route('/logs')
def logs():
    return jsonify(list(LOG_BUFFER))

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Configuration ---
DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING", 
    "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
).strip("'").strip('"')

# Sport Configuration
# Slug maps to AiScore URL path segments or state keys
SPORTS_CONFIG = {
    'cricket':       {'slug': 'cricket',       'table': 'live_cricket',       'state_key': 'cricket'},
    'football':      {'slug': 'football',      'table': 'live_football',      'state_key': 'football'},
    'tennis':        {'slug': 'tennis',        'table': 'live_tennis',        'state_key': 'tennis'},
    'basketball':    {'slug': 'basketball',    'table': 'live_basketball',    'state_key': 'basketball'}, 
    'table-tennis':  {'slug': 'table-tennis',  'table': 'live_table_tennis',  'state_key': 'tabletennis'},
    'ice-hockey':    {'slug': 'ice-hockey',    'table': 'live_ice_hockey',    'state_key': 'icehockey'},
    'esports':       {'slug': 'esports',       'table': 'live_esports',       'state_key': 'esports'},
}


# --- Database Setup ---
def initialize_db():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        # Schema already exists from previous runs/setup
        log_msg("[SUCCESS] Connected to NeonDB.")
        return conn
    except Exception as e:
        log_msg(f"[ERROR] Database initialization failed: {e}")
        SCRAPER_STATS['last_error'] = str(e)
        return None

# --- AiScore Formatting Helpers ---

def format_score_aiscore(sport, match):
    """
    Parses score from AiScore match object for different sports.
    """
    try:
        if sport == 'cricket':
             scores = match.get('ckScores', {})
             innings = scores.get('innings', [])
             
             h_score = "0"
             a_score = "0"
             
             # Map innings to home(1) and away(2)
             for inn in innings:
                 runs = inn.get('runs', 0)
                 wickets = inn.get('wickets', 0)
                 overs = round(inn.get('overs', 0), 1)
                 belong = inn.get('belong', 0)
                 
                 fmt = f"{runs}/{wickets} ({overs})"
                 
                 if belong == 1: h_score = fmt
                 elif belong == 2: a_score = fmt
                 
             if not innings:
                 # Fallback to ft
                 ft = scores.get('ft', [])
                 if ft and len(ft) >= 2:
                     h_score = str(ft[0])
                     a_score = str(ft[1])
                     
             return f"{h_score} vs {a_score}"
        
        # Tennis, Table Tennis, Ice Hockey, Basketball, Esports, Football
        # These use 'score' field or 'homeScore'/'awayScore'
        home_score = match.get('homeScore', match.get('home_score', ''))
        away_score = match.get('awayScore', match.get('away_score', ''))
        
        # Sometimes score is in a nested 'score' object
        if not home_score and not away_score:
            score_obj = match.get('score', {})
            if isinstance(score_obj, dict):
                home_score = score_obj.get('home', score_obj.get('h', ''))
                away_score = score_obj.get('away', score_obj.get('a', ''))
        
        # Fallback to 'scores' array [home, away]
        if not home_score and not away_score:
            scores = match.get('scores', [])
            if isinstance(scores, list) and len(scores) >= 2:
                home_score = str(scores[0])
                away_score = str(scores[1])
                
        # Fallback to 'ft' (final/total)
        if not home_score and not away_score:
            ft = match.get('ft', [])
            if isinstance(ft, list) and len(ft) >= 2:
                home_score = str(ft[0])
                away_score = str(ft[1])
        
        if home_score or away_score:
            return f"{home_score} - {away_score}"
        
        return "0 - 0"
        
    except Exception as e:
        return "?"

def get_batting_team(match, home_team, away_team):
    """
    Determines current batting team for cricket matches.
    """
    try:
        scores = match.get('ckScores', {})
        innings = scores.get('innings', [])
        
        if innings:
            # Last innings is current
            last_inn = innings[-1]
            belong = last_inn.get('belong', 0)
            
            if belong == 1: return home_team
            elif belong == 2: return away_team
    except:
        pass
    return None

def get_team_name(match, side='home', team_map=None):

    team_obj = match.get(f"{side}Team", {})
    if 'name' in team_obj and team_obj['name']: return team_obj['name']
    
    tid = team_obj.get('id')
    if team_map and tid in team_map:
        return team_map[tid]
        
    return "Unknown"

def get_odds(match):
    """
    Extracts odds from AiScore match object.
    Returns dict with home_odds, away_odds, draw_odds
    """
    odds = {'home': None, 'away': None, 'draw': None}
    
    try:
        ext = match.get('ext', {})
        odds_data = ext.get('odds', {})
        odd_items = odds_data.get('oddItems', [])
        
        # oddItems[1] typically contains the main odds
        # odd array: [home_odds, draw_odds(?), away_odds, ?]
        if len(odd_items) > 1 and odd_items[1]:
            odd_arr = odd_items[1].get('odd', [])
            if len(odd_arr) >= 3:
                odds['home'] = odd_arr[0] if odd_arr[0] and odd_arr[0] != '0' else None
                odds['away'] = odd_arr[2] if odd_arr[2] and odd_arr[2] != '0' else None
                # Draw odds might be at index 1 for football
                if len(odd_arr) > 1 and odd_arr[1] and odd_arr[1] != '0':
                    odds['draw'] = odd_arr[1]
    except:
        pass
        
    return odds

# --- Main Scraper Logic ---

def fetch_aiscore_live(page, sport_slug, state_key):
    matches = []
    
    # URL Selection
    if sport_slug == 'football':
         url = f"https://www.aiscore.com/{sport_slug}/live"
    else:
         url = f"https://www.aiscore.com/{sport_slug}"
    
    try:
        if page.is_closed(): return []
        
        response = page.goto(url, timeout=30000, wait_until='domcontentloaded')
        
        # Brief wait for dynamic content (1s instead of 3s to avoid timeout issues)
        if sport_slug == 'football':
            page.wait_for_timeout(4000)
        else:
            page.wait_for_timeout(1000)
        
        # Extract __NUXT__
        data = page.evaluate("""() => {
            if (window.__NUXT__) return window.__NUXT__;
            return null;
        }""")
        
        if data:
            state = data.get('state', {})
            sport_state = state.get(state_key, {})
            
            # 1. Build Team Map
            team_map = {}
            # Try matchesFuture
            if 'MatchesFuture' in state:
                for t in state['MatchesFuture'].get('teams', []):
                    team_map[t['id']] = t['name']
            
            # Try matchesData_teams (Live)
            if 'matchesData_teams' in sport_state:
                for t in sport_state['matchesData_teams']:
                    team_map[t['id']] = t['name']
            
            # Debug Keys
            log_msg(f"[DEBUG] {sport_slug} keys: {list(sport_state.keys())}")
            
            # 2. Find Matches
            found_matches = []
            if 'matchesData_matches' in sport_state:
                found_matches = sport_state['matchesData_matches']
            elif 'matches' in sport_state:
                found_matches = sport_state['matches']
            
            # Football: state.football['home-new']['matchesData']
            if not found_matches:
                home_new = sport_state.get('home-new', {})
                if 'matchesData' in home_new:
                    m_data = home_new['matchesData']
                    if isinstance(m_data, list):
                        found_matches = m_data
                    elif isinstance(m_data, dict):
                        # 1. Direct key
                        if 'matches' in m_data:
                            found_matches = m_data['matches']
                        else:
                            # 2. Nested competitions (iterate values)
                            nested_matches = []
                            for k, v in m_data.items():
                                if isinstance(v, dict) and 'matches' in v:
                                    nested_matches.extend(v['matches'])
                            
                            if nested_matches:
                                found_matches = nested_matches
            
            log_msg(f"[DEBUG] {sport_slug}: Found {len(found_matches)} matches in state.")
            
            for m in found_matches:
                m['home_name_resolved'] = get_team_name(m, 'home', team_map)
                m['away_name_resolved'] = get_team_name(m, 'away', team_map)
                matches.append(m)
                
        else:
            log_msg(f"[WARN] __NUXT__ not found for {sport_slug}")
            
    except Exception as e:
        log_msg(f"[WARN] Fetch {sport_slug} failed: {e}")
        SCRAPER_STATS['last_error'] = f"Fetch {sport_slug}: {str(e)}"
        
    return matches


def upsert_matches(conn, sport_key, matches):
    if not matches: return []
    
    ids = []
    config = SPORTS_CONFIG[sport_key]
    table_name = config['table']
    
    try:
        cur = conn.cursor()
        count = 0
        
        for m in matches:
            match_id = str(m.get('id'))
            ids.append(match_id)
            
            # Basic Info
            home_team = m.get('home_name_resolved', 'Unknown')
            away_team = m.get('away_name_resolved', 'Unknown')
            
            # Status
            # Status
            status_code = m.get('matchStatus', 0)
            status_map = {
                1: "Upcoming",
                2: "Live",
                3: "Finished",
                4: "Postponed",
                5: "Cancelled",
                6: "Interrupted",
                7: "Abandoned",
                8: "Finished", # Retired
                9: "Walkover",
                11: "Halftime", # Sometimes used
                12: "Extra Time",
                13: "Penalties"
            }
            if status_code in status_map:
                status = status_map[status_code]
            else:
                # Fallback
                if status_code > 2: status = "Finished"
                else: status = "Upcoming"
            
            # Live only if code is 2 or specifically representing active play
            is_live = (status_code == 2 or status in ["Live", "Halftime", "Extra Time", "Penalties"])
            
            # Formatted Score
            score_str = format_score_aiscore(sport_key, m)
            
            # Extract basic scores for columns if possible (fallback to split)
            h_score = "?"
            a_score = "?"
            # Try to parse from string if it follows "A vs B" or "A - B" format
            if " vs " in score_str:
                parts = score_str.split(" vs ")
                if len(parts) == 2:
                    h_score, a_score = parts
            elif " - " in score_str:
                parts = score_str.split(" - ")
                if len(parts) == 2:
                    h_score, a_score = parts
            
            # Batting Team (Cricket only)
            batting_team = None
            if sport_key == 'cricket':
                batting_team = get_batting_team(m, home_team, away_team)
            
            # Extract Odds
            odds = get_odds(m)

            
            # Upsert
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
                batting_team, is_live, h_score, a_score,
                odds['home'], odds['away'], odds['draw']
            ))


            
            count += 1
            
        conn.commit()
        if count > 0:
            log_msg(f"[SYNC] {sport_key}: Upserted {count} matches.")
            # Update Stats
            if sport_key not in SCRAPER_STATS['sports']:
                SCRAPER_STATS['sports'][sport_key] = {}
            SCRAPER_STATS['sports'][sport_key]['last_sync'] = str(datetime.now())
            SCRAPER_STATS['sports'][sport_key]['matches'] = count
            
    except Exception as e:
        log_msg(f"[DB ERROR] {sport_key}: {e}")
        SCRAPER_STATS['last_error'] = f"DB Error {sport_key}: {str(e)}"
        conn.rollback()
        
    return ids

def cleanup_stale_matches(conn, sport_key, active_ids):
    """
    Marks matches as 'Finished' if they are no longer in the live feed.
    This handles matches that finished and disappeared from AiScore.
    """
    if not active_ids:
        return
    
    config = SPORTS_CONFIG[sport_key]
    table_name = config['table']
    
    try:
        cur = conn.cursor()
        
        # Find matches that are marked as 'Live' but not in the active set
        placeholders = ','.join(['%s'] * len(active_ids))
        cur.execute(f"""
            UPDATE {table_name}
            SET status = 'Finished', is_live = FALSE, last_updated = NOW()
            WHERE is_live = TRUE 
            AND match_id NOT IN ({placeholders});
        """, active_ids)
        
        updated = cur.rowcount
        if updated > 0:
            log_msg(f"[CLEANUP] {sport_key}: Marked {updated} stale matches as Finished.")
        
        conn.commit()
        
    except Exception as e:
        log_msg(f"[CLEANUP ERROR] {sport_key}: {e}")
        conn.rollback()

# --- Supervisor ---


def run_scraper():
    while True:
        log_msg("[SUPERVISOR] Starting AiScore Scraper Loop...")
        conn = None
        browser = None
        
        try:
            conn = initialize_db()
            if not conn:
                time.sleep(10)
                continue

            log_msg("[DEBUG] Launching Playwright...")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )
                
                # 1. Desktop Context (For Basketball)
                context_desktop = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page_desktop = context_desktop.new_page()
                
                # 2. Mobile Context (For Everything Else)
                iphone = p.devices['iPhone 12']
                context_mobile = browser.new_context(**iphone)
                page_mobile = context_mobile.new_page()
                
                log_msg("[DEBUG] Pages created (Mobile + Desktop). Entering main loop.")
                
                cycle_count = 0
                max_cycles = 50 
                
                while True:
                    start_time = time.time()
                    
                    for sport, config in SPORTS_CONFIG.items():
                        try:
                            if conn.closed: raise Exception("DB Conn Closed")

                            log_msg(f"[DEBUG] Fetching {sport}...")
                            
                            # Select page based on sport
                            if sport == 'basketball':
                                target_page = page_desktop
                            else:
                                target_page = page_mobile
                                
                            matches = fetch_aiscore_live(target_page, config['slug'], config['state_key'])
                            
                            if matches:
                                active_ids = upsert_matches(conn, sport, matches)
                                cleanup_stale_matches(conn, sport, active_ids)
                            else:
                                # No live matches, mark all as finished
                                cleanup_stale_matches(conn, sport, [])

                            
                        except Exception as e:
                            log_msg(f"[ERROR] {sport}: {e}")
                            SCRAPER_STATS['last_error'] = str(e)
                            if "closed" in str(e).lower() or "connection" in str(e).lower():
                                raise e
                    
                    elapsed = time.time() - start_time
                    sleep_time = max(10.0, 30.0 - elapsed)
                    time.sleep(sleep_time) 
                    
                    cycle_count += 1
                    if cycle_count >= max_cycles: 
                        log_msg(f"[SUPERVISOR] Scheduled Restart...")
                        break

        except Exception as e:
            log_msg(f"[CRASH] Supervisor exception: {e}")
            log_msg(traceback.format_exc())
            SCRAPER_STATS['last_error'] = str(e)
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
