import time
import json
import os
import psycopg2
from psycopg2.extras import Json
import threading
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
import traceback
import hashlib

def get_deterministic_hash(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

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
        
        # SPECIAL: Basketball (Sum of Quarters)
        if sport == 'basketball':
             h_list = match.get('homeScores', [])
             a_list = match.get('awayScores', [])
             if h_list and a_list:
                 try:
                     # Sum strictly numeric values
                     h_total = sum([int(x) for x in h_list if str(x).isdigit()])
                     a_total = sum([int(x) for x in a_list if str(x).isdigit()])
                     if h_total > 0 or a_total > 0:
                         return f"{h_total} - {a_total}"
                 except: pass

        # SPECIAL: Tennis (Show Sets + Current Set needed?)
        # For now, if homeScore/awayScore is 0-0, check if we have set scores
        if sport == 'tennis' and (not home_score or str(home_score) == '0') and (not away_score or str(away_score) == '0'):
             s_scores = match.get('homeScores', [])
             if s_scores:
                 # Usually these are games per set.
                 # If we want SET score, we count sets won?
                 # Or just return the sets string e.g. "6-4 2-1"
                 # Let's keep it simple: If main score is 0-0, try to construct from sets?
                 # Actually, usually homeScore IS the set count. Maybe it's 0-0 because it's first set?
                 pass

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
    
    # 0. Pre-extracted odds (e.g. from Soccer24)
    if 'odds' in match and isinstance(match['odds'], dict):
        return match['odds']
    
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
                        # 2. Desktop keys (liveMatches/allMatches)
                        elif 'liveMatches' in m_data:
                            found_matches = m_data['liveMatches']
                        elif 'allMatches' in m_data:
                            found_matches = m_data['allMatches']
                        else:
                            # 3. Nested competitions (iterate values)
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
        
        for i, m in enumerate(matches):
            if i == 0:
                log_msg(f"[DEBUG] Match keys: {list(m.keys())}")
                if sport_key == 'football':
                     log_msg(f"[DEBUG] Football sample: {m}")

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
        log_msg(f"[DEBUG] cleanup {sport_key}: No active IDs.")
        return
    
    config = SPORTS_CONFIG[sport_key]
    table_name = config['table']
    
    try:
        log_msg(f"[DEBUG] cleanup {sport_key} starting...") 
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

# --- Soccer24 Scraper (Football Fallback) ---
def fetch_soccer24(page):
    log_msg("[DEBUG] fetch_soccer24: Entry")
    url = "https://www.soccer24.com/"
    matches = []
    try:
        if page.is_closed(): 
            log_msg("[ERROR] Page is closed!")
            return []
        log_msg(f"[DEBUG] Navigating to {url}...")
        page.goto(url, timeout=45000, wait_until='domcontentloaded')
        try: page.wait_for_selector('.event__match', timeout=5000)
        except: pass
        
        # Debug Logs
        title = page.title()
        rows = page.locator('.event__match').all()
        log_msg(f"[DEBUG] Soccer24 Page Title: {title}")
        log_msg(f"[DEBUG] Soccer24 Rows Found: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                # Log progress every 10 rows to detect hangs
                if i % 10 == 0: log_msg(f"[DEBUG] Processing row {i}/{len(rows)}")
                
                if i == 0:
                    log_msg(f"[DEBUG] Row 0 HTML: {row.inner_html()[:500]}...")

                # Extract text INSTANTLY using JS evaluate to avoid locator timeouts
                # Support multiple selector variations (BEM vs legacy/new classes)
                data = row.evaluate("""el => {
                    const getText = (selectors) => {
                        for (let sel of selectors) {
                            let elFound = el.querySelector(sel);
                            if (elFound) return elFound.innerText.replace(/\\n/g, ' ').trim();
                        }
                        return "";
                    };
                    return {
                        home: getText(['.event__participant--home', '.event__homeParticipant']),
                        away: getText(['.event__participant--away', '.event__awayParticipant']),
                        s_h: getText(['.event__score--home', '.event__score--home']),
                        s_a: getText(['.event__score--away', '.event__score--away']),
                        status: getText(['.event__stage', '.event__stage--block']),
                        odd_1: getText(['.event__odd--odd1', '.o_1']),
                        odd_x: getText(['.event__odd--odd2', '.o_0']),
                        odd_2: getText(['.event__odd--odd3', '.o_2'])
                    }
                }""")

                home = data['home']
                away = data['away']
                s_h = data['s_h'] or "0"
                s_a = data['s_a'] or "0"
                status_text = data['status']
                
                # Odds
                o1 = data['odd_1']
                ox = data['odd_x']
                o2 = data['odd_2']
                
                if not home or not away: continue
                
                # Check if live
                # Status examples: "Finished", "Half Time", "30", "90+5", "After Pen."
                is_live = False
                
                # Check for live indicators
                # 1. It's a digit (current minute) e.g. "30"
                if status_text.isdigit():
                    is_live = True
                # 2. Contains "+" (injury time) e.g. "90+4"
                elif "+" in status_text:
                    is_live = True
                # 3. Explicit keywords
                elif "Half Time" in status_text or "Live" in status_text or "HT" in status_text:
                    is_live = True
                
                # Explicit exclusions override everything
                if any(x in status_text for x in ["Finished", "After", "Postponed", "Abandoned", "Scheduled", "FRO"]):
                    is_live = False

                # Debug status for first few rows
                if i < 5: log_msg(f"[DEBUG] Row {i} Status: {status_text} -> Live: {is_live}")
                
                # Normalize to AiScore structure
                
                # Normalize to AiScore structure

                # Normalize to AiScore structure
                match_id = f"s24_{get_deterministic_hash(home+away)}" 
                
                matches.append({
                    'id': match_id,
                    'matchStatus': 2 if is_live else 10, 
                    'statusId': 2 if is_live else 10,
                    'is_live_override': is_live,
                    'status_text_override': status_text,
                    'homeTeam': {'name': home},
                    'awayTeam': {'name': away},
                    'home_name_resolved': home,
                    'away_name_resolved': away,
                    'homeScore': s_h if s_h.isdigit() else 0,
                    'awayScore': s_a if s_a.isdigit() else 0,
                    'sportId': 1,
                    'odds': {
                        'home': float(o1) if o1 and o1.replace('.','',1).isdigit() else 0,
                        'draw': float(ox) if ox and ox.replace('.','',1).isdigit() else 0,
                        'away': float(o2) if o2 and o2.replace('.','',1).isdigit() else 0
                    }
                })
            except: continue
    except Exception as e:
        log_msg(f"[ERROR] Soccer24 Fetch: {e}")
        
    log_msg(f"[DEBUG] Soccer24 Parsed Matches: {len(matches)}")
    return matches

# --- Supervisor ---

def run_scraper():
    while True:
        log_msg("[SUPERVISOR] Starting Scraper Loop...")
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
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-blink-features=AutomationControlled']
                )
                
                # 1. Desktop Context (BASKETBALL + FOOTBALL SOCCER24)
                context_desktop = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                context_desktop.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                page_desktop = context_desktop.new_page()
                
                # 2. Mobile Context (OTHERS)
                iphone = p.devices['iPhone 12']
                context_mobile = browser.new_context(**iphone)
                page_mobile = context_mobile.new_page()
                
                log_msg("[DEBUG] Pages created. Entering main loop.")
                cycle_count = 0
                max_cycles = 50 

                while True:
                    start_time = time.time()
                    if conn.closed: raise Exception("DB Conn Closed")
                    
                    for sport, config in SPORTS_CONFIG.items():
                        try:
                            matches = []
                            # ROUTING
                            if sport == 'football':
                                log_msg("[DEBUG] Fetching football (Soccer24)...")
                                matches = fetch_soccer24(page_desktop)
                            elif sport == 'basketball':
                                log_msg("[DEBUG] Fetching basketball...")
                                matches = fetch_aiscore_live(page_desktop, config['slug'], config['state_key'])
                            else:
                                log_msg(f"[DEBUG] Fetching {sport}...")
                                matches = fetch_aiscore_live(page_mobile, config['slug'], config['state_key'])
                            
                            if matches:
                                log_msg(f"[DEBUG] calling upsert_matches for {sport} with {len(matches)} items")
                                active_ids = upsert_matches(conn, sport, matches)
                                cleanup_stale_matches(conn, sport, active_ids)
                            else:
                                cleanup_stale_matches(conn, sport, [])

                        except Exception as e:
                            log_msg(f"[ERROR] {sport}: {e}")
                    
                    elapsed = time.time() - start_time
                    time.sleep(max(10.0, 30.0 - elapsed))
                    cycle_count += 1
                    if cycle_count >= max_cycles: 
                         log_msg("[SUPERVISOR] Cycling restart...")
                         break
        
        except Exception as e:
            log_msg(f"[CRASH] Supervisor exception: {e}")
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
