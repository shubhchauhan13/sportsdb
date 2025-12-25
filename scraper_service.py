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
import collections
from datetime import datetime

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

# --- Architect Agent API ---
import queue
COMMAND_QUEUE = queue.Queue()

@app.route('/api/force_refresh', methods=['POST'])
def force_refresh():
    try:
        from flask import request
        sport = request.args.get('sport')
        if not sport: return jsonify({"error": "sport required"}), 400
        COMMAND_QUEUE.put({'type': 'FORCE_REFRESH', 'sport': sport})
        log_msg(f"[ARCHITECT] Received FORCE_REFRESH for {sport}")
        return jsonify({"status": "queued", "command": "FORCE_REFRESH", "sport": sport})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/switch_source', methods=['POST'])
def switch_source():
    # Helper to tell scraper to prefer a source for a match/sport
    try:
        from flask import request
        data = request.json or {}
        sport = data.get('sport') # broad switch
        source = data.get('source') # e.g. 'sofascore', 'aiscore'
        
        if sport and source:
            # We can update a global config override
            # For now, just log and queue it
            COMMAND_QUEUE.put({'type': 'SWITCH_SOURCE', 'sport': sport, 'source': source})
            log_msg(f"[ARCHITECT] Received SWITCH_SOURCE for {sport} -> {source}")
            return jsonify({"status": "queued"})
        return jsonify({"error": "sport and source required"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    'volleyball':    {'slug': 'volleyball',    'table': 'live_volleyball',    'state_key': 'volleyball'},
    'baseball':      {'slug': 'baseball',      'table': 'live_baseball',      'state_key': 'baseball'},
    'badminton':     {'slug': 'badminton',     'table': 'live_badminton',     'state_key': 'badminton'},
    'amfootball':    {'slug': 'american-football', 'table': 'live_american_football', 'state_key': 'amfootball'},
    'handball':      {'slug': 'handball',      'table': 'live_handball',      'state_key': 'handball'},
    'water-polo':    {'slug': 'water-polo',    'table': 'live_water_polo',    'state_key': 'waterpolo'},
    'snooker':       {'slug': 'snooker',       'table': 'live_snooker',       'state_key': 'snooker'},
    'rugby':         {'slug': 'rugby',         'table': 'live_rugby',         'state_key': 'rugby'},
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
        ext = match.get('ext') or {}
        odds_data = ext.get('odds') or {}
        odd_items = odds_data.get('oddItems') or []
        
        # Iterate to find the main odds
        # Priority: Index 1 (Match winner usually), then 0 or others
        best_odds = None
        indices_to_check = [1, 0, 2]
        
        for idx in indices_to_check:
            if idx < len(odd_items):
                item = odd_items[idx]
                odd_arr = item.get('odd', [])
                if len(odd_arr) >= 2:
                    # Filter out zero/empty to check validity
                    valid_vals = [v for v in odd_arr if v and str(v) != '0']
                    if len(valid_vals) >= 2:
                        best_odds = odd_arr
                        break
        
        if best_odds and len(best_odds) >= 2:
            def clean(v):
                return v if v and str(v) != '0' else None

            # H, D, A mapping
            odds['home'] = clean(best_odds[0])
            
            if len(best_odds) >= 3:
                odds['draw'] = clean(best_odds[1])
                odds['away'] = clean(best_odds[2])
            elif len(best_odds) == 2:
                # Assuming H, A
                odds['away'] = clean(best_odds[1])

            # Special case for Basketball/Tennis often D is 0 in 3-item list, so index 2 is Away
            if not odds['away'] and len(best_odds) > 2:
                 odds['away'] = clean(best_odds[2])

    except Exception as e:
        log_msg(f"[ERROR] get_odds: {e}")
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
            other_odds_val = None
            
            # Football: Use standard columns
            # Others: Use other_odds column, set standard columns to None
            # Football: Use standard columns
            # Others: Use standard columns AND other_odds column
            other_odds_val = odds 
            
            if i == 0:
                pass
                # log_msg(f"[DEBUG] {sport_key} first match odds extraction: {other_odds_val}")
            
            # Upsert
            cur.execute(f"""
                INSERT INTO {table_name} (
                    match_id, match_data, home_team, away_team, status, score, 
                    batting_team, is_live, home_score, away_score,
                    home_odds, away_odds, draw_odds, other_odds, last_updated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
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
                    last_updated = NOW(),
                    home_odds = CASE WHEN EXCLUDED.home_odds IS NOT NULL THEN EXCLUDED.home_odds ELSE {table_name}.home_odds END,
                    away_odds = CASE WHEN EXCLUDED.away_odds IS NOT NULL THEN EXCLUDED.away_odds ELSE {table_name}.away_odds END,
                    draw_odds = CASE WHEN EXCLUDED.draw_odds IS NOT NULL THEN EXCLUDED.draw_odds ELSE {table_name}.draw_odds END,
                    other_odds = CASE 
                        WHEN (EXCLUDED.other_odds->>'home' IS NOT NULL AND EXCLUDED.other_odds->>'home' != 'None') 
                        THEN EXCLUDED.other_odds 
                        ELSE {table_name}.other_odds 
                    END;
            """, (
                match_id, Json(m), home_team, away_team, status, score_str, 
                batting_team, is_live, h_score, a_score,
                odds['home'], odds['away'], odds['draw'], Json(odds)
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


    log_msg(f"[DEBUG] Soccer24 Parsed Matches: {len(matches)}")
    return matches

# --- Sofascore Scraper (Table Tennis) ---
def fetch_sofascore_table_tennis(page):
    log_msg("[DEBUG] fetch_sofascore_table_tennis: Entry")
    # 1. Fetch Live List
    list_url = "https://www.sofascore.com/api/v1/sport/table-tennis/events/live"
    matches = []
    
    try:
        # We use goto with JSON response interception manually or just expect JSON on page
        # Getting JSON via page.goto works if the browser renders it (which Chrome does) -> innerText
        # BUT explicitly waiting for the response is cleaner.
        # Let's use the direct response extraction
        
        response = page.goto(list_url, timeout=30000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[ERROR] Sofascore list fetch failed: {response.status}")
            return []
            
        try:
            data = response.json()
        except:
             # Fallback: Extract from body text (sometimes browser wraps it in pre)
            text = page.locator("body").inner_text()
            data = json.loads(text)
            
        events = data.get('events', [])
        log_msg(f"[DEBUG] Sofascore TT: Found {len(events)} live events.")
        
        for i, ev in enumerate(events):
            try:
                mid = str(ev.get('id'))
                home = ev.get('homeTeam', {}).get('name', 'Unknown')
                away = ev.get('awayTeam', {}).get('name', 'Unknown')
                
                # Scores
                h_score = str(ev.get('homeScore', {}).get('current', 0))
                a_score = str(ev.get('awayScore', {}).get('current', 0))
                
                # Status
                status_desc = ev.get('status', {}).get('description', 'Live')
                
                # Fetch Odds (with delay to be polite)
                # limit to first 20 to avoid timeouts if list is huge
                if i < 20:
                    time.sleep(0.5) 
                    odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    
                    try:
                        o_resp = page.goto(odds_url, timeout=10000, wait_until='domcontentloaded')
                        if o_resp.ok:
                            o_json = o_resp.json()
                            markets = o_json.get('markets', [])
                            for m in markets:
                                # Look for Winner (marketName usually 'Winner' or 'Full time')
                                if m.get('isMain') or m.get('marketName') in ['Winner', 'Full time']:
                                    choices = m.get('choices', [])
                                    if len(choices) >= 2:
                                        # Assuming 1=Home, 2=Away
                                        # fractionalValue looks like "8/15", decimalValue needed
                                        # Usually choice has 'fractionalValue' and we want decimal?
                                        # Or extract from 'value' which might be missing in some views?
                                        # Let's try to find decimal value if available, or just store string
                                        
                                        # Simplification: Store fractional or whatever comes
                                        # Sofascore JSON usually has: choices: [{name: '1', fractionalValue: '...', oldOdds: ...}]
                                        # We prefer decimal. Convert? 
                                        # Let's check keys from our verify script. choices elements have 'fractionalValue'.
                                        # If available, grab the cleanest.
                                        
                                        # Actually, just grab fractionalValue for now or convert.
                                        def parse_frac(s):
                                            if '/' in s:
                                                n, d = s.split('/')
                                                return round(1 + int(n)/int(d), 2)
                                            return s

                                        odds_data['home'] = choices[0].get('fractionalValue')
                                        odds_data['away'] = choices[1].get('fractionalValue')
                                        
                                        # Try to convert to decimal for compatibility
                                        try:
                                             odds_data['home'] = str(parse_frac(odds_data['home']))
                                             odds_data['away'] = str(parse_frac(odds_data['away']))
                                        except: pass
                                        break
                    except Exception as oe:
                        # log_msg(f"[WARN] Failed to fetch odds for {mid}: {oe}")
                        pass
                else:
                    odds_data = None # Skip odds for overflow to save time

                # Construct Match Object
                matches.append({
                    'id': f"sf_{mid}", # Prefix to distinguish from AiScore IDs
                    'matchStatus': 2, # Live
                    'statusId': 2,
                    'is_live_override': True,
                    'status_text_override': status_desc,
                    'homeTeam': {'name': home},
                    'awayTeam': {'name': away},
                    'home_name_resolved': home,
                    'away_name_resolved': away,
                    'homeScore': h_score,
                    'awayScore': a_score,
                    'sportId': 11, # Table Tennis internal ID
                    'odds': odds_data if odds_data else {'home': None, 'away': None, 'draw': None},
                    'match_data_extra': ev # Store full raw sofa event
                })

            except Exception as e:
                log_msg(f"[ERROR] Sofascore parse error match {i}: {e}")
                continue

    except Exception as e:
        log_msg(f"[ERROR] Sofascore TT Fetch: {e}")
        
    log_msg(f"[DEBUG] Sofascore TT: Parsed {len(matches)} matches.")
    return matches

# --- Sofascore Scraper (Esports) ---
def fetch_sofascore_esports(page):
    log_msg("[DEBUG] fetch_sofascore_esports: Entry")
    list_url = "https://www.sofascore.com/api/v1/sport/esports/events/live"
    matches = []
    
    try:
        response = page.goto(list_url, timeout=30000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[ERROR] Sofascore Esports list fetch failed: {response.status}")
            return []
            
        try:
            data = response.json()
        except:
            text = page.locator("body").inner_text()
            data = json.loads(text)
            
        events = data.get('events', [])
        log_msg(f"[DEBUG] Sofascore Esports: Found {len(events)} live events.")
        
        for i, ev in enumerate(events):
            try:
                mid = str(ev.get('id'))
                home = ev.get('homeTeam', {}).get('name', 'Unknown')
                away = ev.get('awayTeam', {}).get('name', 'Unknown')
                
                h_score = str(ev.get('homeScore', {}).get('current', 0))
                a_score = str(ev.get('awayScore', {}).get('current', 0))
                status_desc = ev.get('status', {}).get('description', 'Live')
                
                # Enhanced Odds Extraction with multiple fallbacks
                odds_data = {'home': None, 'away': None, 'draw': None}
                if i < 20: 
                    time.sleep(0.5 + (i % 3) * 0.2)  # Randomized delay for anti-ban
                    odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                    try:
                        o_resp = page.goto(odds_url, timeout=10000)
                        if o_resp.ok:
                            o_json = o_resp.json()
                            markets = o_json.get('markets', [])
                            
                            log_msg(f"[DEBUG] Esports {mid}: Found {len(markets)} markets")
                            
                            for m in markets:
                                market_name = m.get('marketName', '')
                                is_main = m.get('isMain', False)
                                
                                # Check for main winner markets
                                if is_main or market_name in ['Winner', 'Match Winner', 'Full time', 'Map 1 Winner', 'To Win Match', 'Money Line']:
                                    choices = m.get('choices', [])
                                    if len(choices) >= 2:
                                        # Try multiple value keys
                                        home_val = None
                                        away_val = None
                                        
                                        for val_key in ['decimalValue', 'fractionalValue', 'initialValue', 'odds']:
                                            if home_val is None:
                                                home_val = choices[0].get(val_key)
                                            if away_val is None:
                                                away_val = choices[1].get(val_key)
                                        
                                        if home_val and away_val:
                                            odds_data['home'] = home_val
                                            odds_data['away'] = away_val
                                            log_msg(f"[DEBUG] Esports {mid}: Found odds H={home_val} A={away_val}")
                                            break
                                            
                            # Fallback: Check vote/crowdsourcing data
                            if not odds_data['home']:
                                vote = ev.get('vote', {})
                                vote_home = vote.get('vote1')
                                vote_away = vote.get('vote2')
                                if vote_home and vote_away:
                                    # Convert votes to implied odds
                                    try:
                                        total = vote_home + vote_away
                                        if total > 0:
                                            odds_data['home'] = round(total / vote_home, 2) if vote_home > 0 else None
                                            odds_data['away'] = round(total / vote_away, 2) if vote_away > 0 else None
                                            log_msg(f"[DEBUG] Esports {mid}: Derived odds from votes")
                                    except: pass
                                    
                    except Exception as e:
                        log_msg(f"[DEBUG] Esports odds fetch error {mid}: {e}")
                
                matches.append({
                    'id': f"sf_{mid}",
                    'matchStatus': 2,
                    'statusId': 2,
                    'is_live_override': True,
                    'status_text_override': status_desc,
                    'homeTeam': {'name': home},
                    'awayTeam': {'name': away},
                    'home_name_resolved': home,
                    'away_name_resolved': away,
                    'homeScore': h_score,
                    'awayScore': a_score,
                    'sportId': 99,
                    'odds': odds_data,
                    'match_data_extra': ev
                })
            except: continue
            
    except Exception as e:
        log_msg(f"[ERROR] Sofascore Esports Fetch: {e}")
        
    return matches

# --- FlashScore Ice Hockey Scraper (Enterprise) ---

# Anti-ban: User-Agent rotation pool
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

import random

def get_random_ua():
    return random.choice(USER_AGENTS)

def fetch_flashscore_ice_hockey(page):
    """Fetches Ice Hockey odds from FlashScore with anti-ban measures."""
    log_msg("[DEBUG] fetch_flashscore_ice_hockey: Entry")
    matches = []
    
    try:
        # Set random user agent
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        
        # Random delay before request
        time.sleep(random.uniform(1.0, 2.5))
        
        # FlashScore Ice Hockey live page
        url = "https://www.flashscore.com/ice-hockey/"
        response = page.goto(url, timeout=30000, wait_until='networkidle')
        
        if not response.ok:
            log_msg(f"[ERROR] FlashScore Ice Hockey fetch failed: {response.status}")
            return []
        
        # Wait for content to load
        time.sleep(2)
        
        # Extract live matches via data attributes
        try:
            live_rows = page.locator('[class*="event__match--live"]').all()
            log_msg(f"[DEBUG] FlashScore Ice Hockey: Found {len(live_rows)} live matches")
            
            for i, row in enumerate(live_rows[:30]):
                try:
                    time.sleep(random.uniform(0.1, 0.3))  # Anti-ban micro-delay
                    
                    match_id = row.get_attribute('id') or f"fs_{i}"
                    match_id = match_id.replace('g_1_', 'fs_')
                    
                    home_el = row.locator('[class*="event__homeParticipant"]').first
                    away_el = row.locator('[class*="event__awayParticipant"]').first
                    
                    home = home_el.inner_text() if home_el else "Unknown"
                    away = away_el.inner_text() if away_el else "Unknown"
                    
                    home_score_el = row.locator('[class*="event__score--home"]').first
                    away_score_el = row.locator('[class*="event__score--away"]').first
                    
                    h_score = home_score_el.inner_text() if home_score_el else "0"
                    a_score = away_score_el.inner_text() if away_score_el else "0"
                    
                    status_el = row.locator('[class*="event__stage"]').first
                    status = status_el.inner_text() if status_el else "Live"
                    
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    try:
                        odds_els = row.locator('[class*="odds__odd"]').all()
                        if len(odds_els) >= 2:
                            odds_data['home'] = odds_els[0].inner_text()
                            odds_data['away'] = odds_els[-1].inner_text()
                            if len(odds_els) >= 3:
                                odds_data['draw'] = odds_els[1].inner_text()
                    except: pass
                    
                    matches.append({
                        'id': match_id,
                        'matchStatus': 2,
                        'statusId': 2,
                        'is_live_override': True,
                        'status_text_override': status,
                        'homeTeam': {'name': home},
                        'awayTeam': {'name': away},
                        'home_name_resolved': home,
                        'away_name_resolved': away,
                        'homeScore': h_score,
                        'awayScore': a_score,
                        'sportId': 4,
                        'odds': odds_data,
                        'match_data_extra': {}
                    })
                except Exception as e:
                    continue
                    
        except Exception as e:
            log_msg(f"[ERROR] FlashScore DOM parsing: {e}")
            
    except Exception as e:
        log_msg(f"[ERROR] FlashScore Ice Hockey Fetch: {e}")
        
    return matches


# --- OddsPortal Scraper (Optimized) ---

def fetch_oddsportal_hockey(page):
    """Fetches Ice Hockey odds from OddsPortal with optimized wait strategies."""
    log_msg("[DEBUG] fetch_oddsportal_hockey: Entry")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        # Try Live page first
        url = "https://www.oddsportal.com/hockey/live/"
        response = page.goto(url, timeout=30000, wait_until='domcontentloaded') # Relaxed wait
        
        if not response or not response.ok:
            log_msg(f"[ERROR] OddsPortal Hockey fetch failed: {response.status if response else 'No Response'}")
            return []
        
        # Wait for either row selector or specific element
        try:
            page.wait_for_selector('div[class*="eventRow"]', timeout=10000)
        except:
            log_msg("[DEBUG] OddsPortal Hockey: No event rows found immediately.")
            
        time.sleep(2) # Give JS time to hydrate
        
        try:
            rows = page.locator('div[class*="eventRow"]').all()
            log_msg(f"[DEBUG] OddsPortal Hockey: Found {len(rows)} matches")
            
            for i, row in enumerate(rows[:30]):
                try:
                    # Quick check if it's a live match row
                    if not row.is_visible(): continue
                    
                    teams_el = row.locator('a[class*="participant"]').all()
                    if len(teams_el) >= 2:
                        home = teams_el[0].inner_text().strip()
                        away = teams_el[1].inner_text().strip()
                    else:
                        continue
                        
                    # Extract Odds (Home, Draw, Away)
                    # OddsPortal often puts them in specific column order
                    odds_els = row.locator('div[class*="odds-value"]').all()
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    
                    if len(odds_els) >= 2:
                        odds_data['home'] = odds_els[0].inner_text().strip()
                        odds_data['away'] = odds_els[-1].inner_text().strip()
                        if len(odds_els) >= 3:
                            odds_data['draw'] = odds_els[1].inner_text().strip()
                    
                    # Skip if no odds found
                    if not odds_data['home'] and not odds_data['away']:
                        continue
                        
                    match_id = f"op_hackey_{i}_{get_deterministic_hash(home+away)[:8]}"
                    
                    matches.append({
                        'id': match_id,
                        'matchStatus': 2,
                        'statusId': 2,
                        'is_live_override': True,
                        'status_text_override': 'Live',
                        'homeTeam': {'name': home},
                        'awayTeam': {'name': away},
                        'home_name_resolved': home,
                        'away_name_resolved': away,
                        'homeScore': '?',
                        'awayScore': '?',
                        'sportId': 4,
                        'odds': odds_data,
                        'match_data_extra': {'source': 'ODDSPARTAL'}
                    })
                except: continue
                
        except Exception as e:
             log_msg(f"[ERROR] OddsPortal row parsing: {e}")

    except Exception as e:
        log_msg(f"[ERROR] OddsPortal Hockey Fetch: {e}")
        
    return matches


def fetch_oddsportal_esports(page):
    """Fetches Esports odds from OddsPortal with optimized wait strategies."""
    log_msg("[DEBUG] fetch_oddsportal_esports: Entry")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        url = "https://www.oddsportal.com/esports/live/"
        response = page.goto(url, timeout=30000, wait_until='domcontentloaded')
        
        if not response or not response.ok:
             log_msg(f"[ERROR] OddsPortal Esports fetch failed: {response.status if response else 'No Resp'}")
             return []
        
        try:
             page.wait_for_selector('div[class*="eventRow"]', timeout=10000)
        except: pass
            
        time.sleep(2)
        
        try:
            rows = page.locator('div[class*="eventRow"]').all()
            log_msg(f"[DEBUG] OddsPortal Esports: Found {len(rows)} matches")
            
            for i, row in enumerate(rows[:30]):
                try:
                    if not row.is_visible(): continue
                    
                    teams_el = row.locator('a[class*="participant"]').all()
                    if len(teams_el) >= 2:
                        home = teams_el[0].inner_text().strip()
                        away = teams_el[1].inner_text().strip()
                    else: continue
                    
                    odds_els = row.locator('div[class*="odds-value"]').all()
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    
                    if len(odds_els) >= 2:
                        odds_data['home'] = odds_els[0].inner_text().strip()
                        odds_data['away'] = odds_els[-1].inner_text().strip()
                        
                    if not odds_data['home'] and not odds_data['away']:
                        continue
                    
                    match_id = f"op_esports_{i}_{get_deterministic_hash(home+away)[:8]}"
                    
                    matches.append({
                        'id': match_id,
                        'matchStatus': 2,
                        'statusId': 2,
                        'is_live_override': True,
                        'status_text_override': 'Live',
                        'homeTeam': {'name': home},
                        'awayTeam': {'name': away},
                        'home_name_resolved': home,
                        'away_name_resolved': away,
                        'homeScore': '?',
                        'awayScore': '?',
                        'sportId': 99,
                        'odds': odds_data,
                        'match_data_extra': {'source': 'ODDSPARTAL'}
                    })
                except: continue
        except Exception as e:
            log_msg(f"[ERROR] OddsPortal Esports parsing: {e}")
            
    except Exception as e:
        log_msg(f"[ERROR] OddsPortal Esports Fetch: {e}")
        
    return matches

def fetch_oddsportal_generic(page, sport_slug, sport_db_id):
    """Fetches odds for Generic sports (Volleyball, Handball, etc) from OddsPortal."""
    log_msg(f"[DEBUG] fetch_oddsportal_generic: Entry for {sport_slug}")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        url = f"https://www.oddsportal.com/{sport_slug}/live/"
        response = page.goto(url, timeout=30000, wait_until='domcontentloaded')
        
        if not response or not response.ok:
             return []
        
        try:
             page.wait_for_selector('div[class*="eventRow"]', timeout=8000)
        except: pass
            
        time.sleep(2)
        
        try:
            rows = page.locator('div[class*="eventRow"]').all()
            log_msg(f"[DEBUG] OddsPortal {sport_slug}: Found {len(rows)} matches")
            
            for i, row in enumerate(rows[:30]):
                try:
                    if not row.is_visible(): continue
                    
                    teams_el = row.locator('a[class*="participant"]').all()
                    if len(teams_el) >= 2:
                        home = teams_el[0].inner_text().strip()
                        away = teams_el[1].inner_text().strip()
                    else: continue
                    
                    odds_els = row.locator('div[class*="odds-value"]').all()
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    
                    if len(odds_els) >= 2:
                        odds_data['home'] = odds_els[0].inner_text().strip()
                        odds_data['away'] = odds_els[-1].inner_text().strip()
                        if len(odds_els) >= 3:
                            odds_data['draw'] = odds_els[1].inner_text().strip()
                        
                    if not odds_data['home'] and not odds_data['away']:
                        continue
                    
                    match_id = f"op_{sport_slug}_{i}_{get_deterministic_hash(home+away)[:8]}"
                    
                    matches.append({
                        'id': match_id,
                        'matchStatus': 2,
                        'statusId': 2,
                        'is_live_override': True,
                        'status_text_override': 'Live',
                        'homeTeam': {'name': home},
                        'awayTeam': {'name': away},
                        'home_name_resolved': home,
                        'away_name_resolved': away,
                        'homeScore': '?',
                        'awayScore': '?',
                        'sportId': sport_db_id,
                        'odds': odds_data,
                        'match_data_extra': {'source': 'ODDSPARTAL'}
                    })
                except: continue
        except: pass
            
    except Exception as e:
        log_msg(f"[ERROR] OddsPortal {sport_slug} Fetch: {e}")
        
    return matches



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
                    # CHECK COMMANDS
                    try:
                        while not COMMAND_QUEUE.empty():
                            cmd = COMMAND_QUEUE.get_nowait()
                            log_msg(f"[ARCHITECT] Processing command: {cmd}")
                            # Logic for FORCE_REFRESH -> Just continue the loop (it scrapes anyway)
                            # Logic for SWITCH_SOURCE -> Update global map (TODO)
                    except: pass
                    
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
                            elif sport == 'table-tennis':
                                log_msg("[DEBUG] Fetching table-tennis (Sofascore)...")
                                matches = fetch_sofascore_table_tennis(page_mobile)
                            elif sport == 'esports':
                                log_msg("[DEBUG] Fetching esports (Sofascore + OddsPortal)...")
                                # Primary: Sofascore, Secondary: OddsPortal for odds
                                matches = fetch_sofascore_esports(page_mobile)
                                # Try OddsPortal to fill in missing odds
                                op_matches = fetch_oddsportal_esports(page_desktop)
                                if op_matches:
                                    log_msg(f"[DEBUG] OddsPortal Esports: Got {len(op_matches)} matches with odds")
                                    # Merge odds from OddsPortal into Sofascore matches  
                                    for m in matches:
                                        if not m.get('odds', {}).get('home'):
                                            # Find matching OddsPortal match by team names
                                            for op in op_matches:
                                                if (m['home_name_resolved'].lower() in op['home_name_resolved'].lower() or 
                                                    op['home_name_resolved'].lower() in m['home_name_resolved'].lower()):
                                                    m['odds'] = op['odds']
                                                    log_msg(f"[DEBUG] Merged odds for {m['home_name_resolved']}")
                                                    break
                            elif sport == 'ice-hockey':
                                log_msg("[DEBUG] Fetching ice-hockey (Multi-source: FlashScore + OddsPortal + AiScore)...")
                                # Multi-source approach for maximum coverage
                                matches = fetch_aiscore_live(page_mobile, config['slug'], config['state_key'])
                                
                                # Try OddsPortal to fill missing odds
                                op_hockey = fetch_oddsportal_hockey(page_desktop)
                                if op_hockey:
                                    log_msg(f"[DEBUG] OddsPortal Hockey: Got {len(op_hockey)} matches with odds")
                                    for m in matches:
                                        if not m.get('odds', {}).get('home'):
                                            for op in op_hockey:
                                                if (m['home_name_resolved'].lower() in op['home_name_resolved'].lower() or 
                                                    op['home_name_resolved'].lower() in m['home_name_resolved'].lower()):
                                                    m['odds'] = op['odds']
                                                    log_msg(f"[DEBUG] Merged Hockey odds for {m['home_name_resolved']}")
                                                    break
                            
                            # --- Minor Sports Routing ---
                            elif sport == 'volleyball':
                                log_msg("[DEBUG] Fetching volleyball (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'volleyball', 13) 
                            elif sport == 'handball':
                                log_msg("[DEBUG] Fetching handball (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'handball', 6)
                            elif sport == 'baseball':
                                log_msg("[DEBUG] Fetching baseball (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'baseball', 3)
                            elif sport == 'snooker':
                                log_msg("[DEBUG] Fetching snooker (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'snooker', 14)
                            elif sport == 'rugby':
                                log_msg("[DEBUG] Fetching rugby (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'rugby-league', 12) # Try league first
                            elif sport == 'water-polo':
                                log_msg("[DEBUG] Fetching water-polo (OddsPortal)...")
                                matches = fetch_oddsportal_generic(page_desktop, 'water-polo', 15)
                             
                            else:
                                log_msg(f"[DEBUG] Generic fetch for {sport}...")
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
    # Start web server thread
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    
    # Run main scraper (blocking)
    run_scraper()
