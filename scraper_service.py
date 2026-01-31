import time
import json
import os
import signal
import sys
import psycopg2
from psycopg2.extras import Json
import threading
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
import traceback
import hashlib
import collections
from datetime import datetime
from fake_useragent import UserAgent
from playwright_stealth import stealth_sync

# Graceful shutdown flag
SHUTDOWN_FLAG = False

def signal_handler(signum, frame):
    global SHUTDOWN_FLAG
    print(f"[SIGNAL] Received signal {signum}. Initiating graceful shutdown...")
    SHUTDOWN_FLAG = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def get_deterministic_hash(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

# --- Global State for Diagnostics ---
SCRAPER_STATS = {
    'started_at': str(datetime.now()),
    'sports': {},
    'workers': {},
    'last_error': None
}
LOG_BUFFER = collections.deque(maxlen=100)

# --- Blocking Detection Tracker ---
BLOCKING_TRACKER = {
    'aiscore': {'consecutive_failures': 0, 'last_success': None, 'last_failure': None, 'last_error': None},
    'soccer24': {'consecutive_failures': 0, 'last_success': None, 'last_failure': None, 'last_error': None},
    'sofascore': {'consecutive_failures': 0, 'last_success': None, 'last_failure': None, 'last_error': None},
    'oddsportal': {'consecutive_failures': 0, 'last_success': None, 'last_failure': None, 'last_error': None},
}
BLOCKING_THRESHOLD = 3  # Mark as blocked after 3 consecutive failures

def record_source_success(source_name):
    """Record a successful fetch from a source, resetting failure count."""
    if source_name in BLOCKING_TRACKER:
        BLOCKING_TRACKER[source_name]['consecutive_failures'] = 0
        BLOCKING_TRACKER[source_name]['last_success'] = str(datetime.now())
        BLOCKING_TRACKER[source_name]['last_error'] = None

def record_source_failure(source_name, error_msg):
    """Record a failed fetch from a source."""
    if source_name in BLOCKING_TRACKER:
        BLOCKING_TRACKER[source_name]['consecutive_failures'] += 1
        BLOCKING_TRACKER[source_name]['last_failure'] = str(datetime.now())
        BLOCKING_TRACKER[source_name]['last_error'] = str(error_msg)[:200]  # Truncate long errors
        
        count = BLOCKING_TRACKER[source_name]['consecutive_failures']
        if count >= BLOCKING_THRESHOLD:
            log_msg(f"[BLOCKING] Source '{source_name}' appears BLOCKED ({count} consecutive failures)")

def get_blocked_sources():
    """Returns list of sources that appear to be blocked."""
    blocked = []
    for source, tracker in BLOCKING_TRACKER.items():
        if tracker['consecutive_failures'] >= BLOCKING_THRESHOLD:
            blocked.append({
                'source': source,
                'failures': tracker['consecutive_failures'],
                'last_error': tracker['last_error'],
                'since': tracker['last_failure']
            })
    return blocked

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

def check_cloudflare(page):
    try:
        title = page.title()
        if "Just a moment" in title or "Attention Required" in title or "Security Check" in title:
            log_msg(f"[CRITICAL] Cloudflare Challenge Detected (Title: {title})")
            return True
        return False
    except:
        return False

@app.route('/health')
def health():
    # 1. Check Worker Heartbeats
    now = datetime.now()
    workers = SCRAPER_STATS.get('workers', {})
    
    stale_workers = []
    worker_status = {}
    
    for w_name, last_beat in workers.items():
        if isinstance(last_beat, str):
            try: last_beat_dt = datetime.strptime(last_beat, "%Y-%m-%d %H:%M:%S")
            except: 
                worker_status[w_name] = {'status': 'unknown', 'last_beat': last_beat}
                continue
        else:
            last_beat_dt = last_beat
            
        delta = (now - last_beat_dt).total_seconds()
        worker_status[w_name] = {
            'status': 'healthy' if delta < 300 else 'stale',
            'last_beat': str(last_beat),
            'seconds_ago': int(delta)
        }
        
        # Threshold: 300 seconds (5 minutes) for HTTP health check failure
        if delta > 300:
            stale_workers.append(f"{w_name} ({int(delta)}s ago)")
            
    # 2. Check Data Staleness (Last Sync)
    sports_stats = SCRAPER_STATS.get('sports', {})
    critical_sports = ['football', 'cricket', 'basketball', 'tennis']
    
    for sport in critical_sports:
        s_stat = sports_stats.get(sport)
        if not s_stat: continue
        
        last_sync = s_stat.get('last_sync')
        if not last_sync: continue
        
        try:
            ls_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S.%f")
        except:
            try: ls_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
            except: continue
            
        delta_sync = (now - ls_dt).total_seconds()
        
        # If a critical sport hasn't synced in 15 mins, something is wrong
        if delta_sync > 900:  # 15 mins
            stale_workers.append(f"DATA_STALE: {sport} ({int(delta_sync)}s)")

    # 3. Check for blocked sources
    blocked_sources = get_blocked_sources()
    
    # Build response
    response_data = {
        "status": "running",
        "uptime_since": SCRAPER_STATS.get('started_at'),
        "workers": worker_status,
        "blocked_sources": blocked_sources,
        "blocking_tracker": BLOCKING_TRACKER,
        "sports_summary": {k: {'matches': v.get('matches', 0), 'last_sync': v.get('last_sync')} 
                          for k, v in sports_stats.items()},
        "logs_tail": list(LOG_BUFFER)[-5:]
    }

    if stale_workers:
        err_msg = f"Unhealthy State: {', '.join(stale_workers)}"
        log_msg(f"[HEALTH] FAILED: {err_msg}")
        response_data["status"] = "unhealthy"
        response_data["error"] = err_msg
        return jsonify(response_data), 500
    
    if blocked_sources:
        response_data["status"] = "degraded"
        response_data["warning"] = f"{len(blocked_sources)} source(s) appear blocked"

    return jsonify(response_data)

@app.route('/logs')
def logs():
    return jsonify(list(LOG_BUFFER))

@app.route('/diagnostics')
def diagnostics():
    """
    Comprehensive diagnostics endpoint for debugging scraper issues.
    Returns full system state including all tracking data.
    """
    try:
        import psutil
        HAS_PSUTIL = True
    except ImportError:
        HAS_PSUTIL = False
    
    now = datetime.now()
    
    # Calculate per-sport status
    sports_status = {}
    for sport, config in SPORTS_CONFIG.items():
        s_stat = SCRAPER_STATS.get('sports', {}).get(sport, {})
        last_sync = s_stat.get('last_sync')
        
        status = 'unknown'
        seconds_since_sync = None
        
        if last_sync:
            try:
                ls_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S.%f")
            except:
                try: ls_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
                except: ls_dt = None
            
            if ls_dt:
                seconds_since_sync = int((now - ls_dt).total_seconds())
                if seconds_since_sync < 120:
                    status = 'active'
                elif seconds_since_sync < 600:
                    status = 'idle'
                else:
                    status = 'stale'
        
        sports_status[sport] = {
            'status': status,
            'matches': s_stat.get('matches', 0),
            'last_sync': last_sync,
            'seconds_since_sync': seconds_since_sync,
            'table': config['table']
        }
    
    # System resources
    if HAS_PSUTIL:
        try:
            memory = psutil.Process().memory_info()
            memory_info = {
                'rss_mb': round(memory.rss / 1024 / 1024, 2),
                'vms_mb': round(memory.vms / 1024 / 1024, 2)
            }
        except Exception as e:
            memory_info = {'error': f'psutil error: {str(e)}'}
    else:
        memory_info = {'error': 'psutil not installed'}
    
    return jsonify({
        'timestamp': str(now),
        'uptime_since': SCRAPER_STATS.get('started_at'),
        'workers': SCRAPER_STATS.get('workers', {}),
        'sports': sports_status,
        'blocking_tracker': BLOCKING_TRACKER,
        'blocked_sources': get_blocked_sources(),
        'last_error': SCRAPER_STATS.get('last_error'),
        'memory': memory_info,
        'logs_recent': list(LOG_BUFFER)[-20:],
        'config': {
            'use_proxy': USE_PROXY,
            'proxy_server': PROXY_CONFIG['server'] if USE_PROXY else None
        }
    })

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
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
).strip("'").strip('"')

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8419641709:AAGKxzGcquExTgYmV4K16T2e3YpvnYPKXCE")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "783170637,1009619021") 

def send_telegram_alert(message):
    """Sends a message to all configured Telegram chat IDs."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log_msg("[ALERT] Telegram not configured. Skipping alert.")
        return
    
    ids = [x.strip() for x in TELEGRAM_CHAT_ID.split(',')]
    
    import requests
    
    for chat_id in ids:
        if not chat_id: continue
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                log_msg(f"[ALERT] Failed to send Telegram to {chat_id}: {resp.text}")
            else:
                log_msg(f"[ALERT] Telegram sent to {chat_id}: {message}")
        except Exception as e:
            log_msg(f"[ALERT] Error sending Telegram to {chat_id}: {message} | {e}")

def monitor_db_freshness():
    """
    Background thread to check if DB is stale (>10 mins) and alert.
    """
    log_msg("[MONITOR] Starting Database Freshness Monitor...")
    
    # Send Test Alert on Startup
    time.sleep(10) # Wait for network
    send_telegram_alert("🚀 **Scraper Service Started**\n\n- Monitoring: Active\n- Server: Railway\n- Alerts: Enabled (>10m staleness)")
    
    time.sleep(60) # Initial grace period
    
    last_alert_map = {} # sport -> last_alert_timestamp
    ALERT_COOLDOWN = 1800 # 30 minutes between alerts for same sport
    STALE_THRESHOLD_SECONDS = 600 # 10 minutes
    
    while not SHUTDOWN_FLAG:
        try:
            conn = initialize_db()
            if not conn:
                time.sleep(60)
                continue
                
            cur = conn.cursor()
            
            # Check all configured sports
            for sport, config in SPORTS_CONFIG.items():
                table = config['table']
                try:
                    # Check max last_updated
                    cur.execute(f"SELECT MAX(last_updated) FROM {table}")
                    res = cur.fetchone()
                    last_update = res[0] if res else None
                    
                    is_stale = False
                    time_diff_str = "N/A"
                    
                    if not last_update:
                        # No data at all? Maybe stale if service running long
                        pass 
                    else:
                        # Handles timezone aware/naive
                        now_db = datetime.now(last_update.tzinfo) if last_update.tzinfo else datetime.now()
                        delta = (now_db - last_update).total_seconds()
                        
                        if delta > STALE_THRESHOLD_SECONDS:
                            is_stale = True
                            time_diff_str = f"{int(delta/60)} mins"
                    
                    if is_stale:
                        # Check cooldown
                        last_sent = last_alert_map.get(sport, 0)
                        if time.time() - last_sent > ALERT_COOLDOWN:
                            msg = f"⚠️ **STALE DATA ALERT** ⚠️\n\nSport: *{sport.upper()}*\nLast Update: {time_diff_str} ago\nServer: Railway"
                            send_telegram_alert(msg)
                            last_alert_map[sport] = time.time()
                            log_msg(f"[MONITOR] Alert sent for {sport}")
                            
                except Exception as e:
                    # Table might not exist yet
                    pass
            
            conn.close()
            
        except Exception as e:
            log_msg(f"[MONITOR] Error: {e}")
            
        time.sleep(60) # Check every minute


# Proxy Configuration (DataImpulse Rotating Residential)
PROXY_CONFIG = {
    'server': os.environ.get('PROXY_SERVER', 'http://gw.dataimpulse.com:823'),
    'username': os.environ.get('PROXY_USERNAME', '448ee9fc87025dfdc8ab'),
    'password': os.environ.get('PROXY_PASSWORD', 'f8fd876b005c06f1'),
}
USE_PROXY = os.environ.get('USE_PROXY', 'false').lower() == 'true'

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
    'motorsport':    {'slug': 'motorsport',    'table': 'live_motorsport',    'state_key': 'motorsport'},
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


def calculate_session_odds(match):
    """
    Calculate session odds/projections from cricket match data.
    
    Returns dict with:
    - run_rate: Current run rate
    - 6_over_projection: Projected runs at 6 overs
    - 10_over_projection: Projected runs at 10 overs
    - 20_over_projection: Projected runs at 20 overs
    - powerplay_runs: Runs scored in first 6 overs (if available)
    - current_runs: Current runs
    - current_overs: Current overs
    - current_wickets: Current wickets
    - session_market: AI-generated session line (e.g., "35.5 runs @ 6 overs")
    """
    session = {
        "run_rate": None,
        "6_over_projection": None,
        "10_over_projection": None,
        "20_over_projection": None,
        "powerplay_runs": None,
        "current_runs": None,
        "current_overs": None,
        "current_wickets": None,
        "session_market": None
    }
    
    try:
        scores = match.get('ckScores', {})
        innings = scores.get('innings', [])
        
        if not innings:
            return session
        
        # Get current innings (last one)
        current_inn = innings[-1]
        runs = current_inn.get('runs', 0)
        wickets = current_inn.get('wickets', 0)
        overs = current_inn.get('overs', 0)
        
        session["current_runs"] = runs
        session["current_wickets"] = wickets
        session["current_overs"] = round(overs, 1)
        
        if overs > 0:
            run_rate = round(runs / overs, 2)
            session["run_rate"] = run_rate
            
            # Projections
            session["6_over_projection"] = round(run_rate * 6, 1)
            session["10_over_projection"] = round(run_rate * 10, 1)
            session["20_over_projection"] = round(run_rate * 20, 1)
            
            # If we're past 6 overs, powerplay is complete
            if overs >= 6:
                # Estimate powerplay runs (usually higher RR in powerplay)
                # This is an approximation since we don't have ball-by-ball
                session["powerplay_runs"] = round(run_rate * 6 * 1.1, 1)  # 10% boost for PP
            else:
                # Current projection for remaining powerplay
                overs_left = 6 - overs
                projected_pp = runs + round(run_rate * overs_left, 1)
                session["powerplay_runs"] = projected_pp
            
            # Generate session market line
            # Standard format: "X runs @ 6 overs" with a line like 35.5
            if overs < 6:
                projected_6 = session["6_over_projection"]
                # Adding typical spread (+/- 0.5)
                session["session_market"] = {
                    "name": "6 Over Runs",
                    "line": projected_6,
                    "over": round(projected_6 + 2, 1),
                    "under": round(projected_6 - 2, 1)
                }
            elif overs < 10:
                projected_10 = session["10_over_projection"]
                session["session_market"] = {
                    "name": "10 Over Runs",
                    "line": projected_10,
                    "over": round(projected_10 + 5, 1),
                    "under": round(projected_10 - 5, 1)
                }
            else:
                projected_20 = session["20_over_projection"]
                session["session_market"] = {
                    "name": "Total Runs",
                    "line": projected_20,
                    "over": round(projected_20 + 10, 1),
                    "under": round(projected_20 - 10, 1)
                }
    
    except Exception as e:
        log_msg(f"[WARN] Session calc error: {e}")
    
    return session

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
        if page.is_closed(): raise Exception("Target page, context or browser has been closed")
        
        response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
        
        # Brief wait for dynamic content (1s instead of 3s to avoid timeout issues)
        if sport_slug == 'football':
            page.wait_for_timeout(4000)
        else:
            page.wait_for_timeout(1000)
            
        if check_cloudflare(page):
            raise Exception("Cloudflare Blocked")
        
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
            return None # Failed to parse state
            
    except Exception as e:
        log_msg(f"[WARN] Fetch {sport_slug} failed: {e}")
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        SCRAPER_STATS['last_error'] = f"Fetch {sport_slug}: {str(e)}"
        return None
        
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
            # Others: Use standard columns AND other_odds column
            other_odds_val = odds 
            
            # Cricket: Add session odds/projections
            if sport_key == 'cricket':
                session_odds = calculate_session_odds(m)
                if session_odds.get('run_rate'):
                    # Merge session data into other_odds
                    other_odds_val = other_odds_val or {}
                    other_odds_val['session'] = session_odds
                    log_msg(f"[SESSION] {home_team} vs {away_team}: RR={session_odds.get('run_rate')}, 6ov={session_odds.get('6_over_projection')}")
            
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
                        WHEN EXCLUDED.other_odds IS NOT NULL AND EXCLUDED.other_odds::text != '{{}}'::text
                        THEN 
                            CASE WHEN {table_name}.other_odds IS NULL THEN EXCLUDED.other_odds
                            ELSE {table_name}.other_odds || EXCLUDED.other_odds 
                            END
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
    config = SPORTS_CONFIG[sport_key]
    table_name = config['table']
    
    try:
        cur = conn.cursor()
        
        if active_ids:
            # Normal cleanup: Mark anything NOT in active_ids as Finished
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
                
        else:
            # CRITICAL FIX: If active_ids is empty (and we reached here), it means
            # the source confirmed there are NO live matches.
            # So, mark ALL currently live matches as Finished.
            log_msg(f"[CLEANUP] {sport_key}: Source returned 0 matches. Marking ALL live as Finished.")
            cur.execute(f"""
                UPDATE {table_name}
                SET status = 'Finished', is_live = FALSE, last_updated = NOW()
                WHERE is_live = TRUE;
            """)
            updated = cur.rowcount
            if updated > 0:
                log_msg(f"[CLEANUP] {sport_key}: Cleared {updated} matches.")
        
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
            raise Exception("Target page, context or browser has been closed")
        log_msg(f"[DEBUG] Navigating to {url}...")
        page.goto(url, timeout=60000, wait_until='domcontentloaded')
        try: page.wait_for_selector('.event__match', timeout=5000)
        except: pass
        
        # Debug Logs
        title = page.title()
        
        # Cloudflare Check
        if check_cloudflare(page):
            raise Exception("Cloudflare Blocked")
            
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
                
                # Parse odds
                home_odds = float(o1) if o1 and o1.replace('.','',1).isdigit() else 0
                draw_odds = float(ox) if ox and ox.replace('.','',1).isdigit() else 0
                away_odds = float(o2) if o2 and o2.replace('.','',1).isdigit() else 0
                
                # Only mark as live if we have valid odds (at least home and away)
                has_valid_odds = home_odds > 0 and away_odds > 0
                effective_is_live = is_live and has_valid_odds
                
                matches.append({
                    'id': match_id,
                    'matchStatus': 2 if effective_is_live else 10, 
                    'statusId': 2 if effective_is_live else 10,
                    'is_live_override': effective_is_live,
                    'status_text_override': status_text,
                    'homeTeam': {'name': home},
                    'awayTeam': {'name': away},
                    'home_name_resolved': home,
                    'away_name_resolved': away,
                    'homeScore': s_h if s_h.isdigit() else 0,
                    'awayScore': s_a if s_a.isdigit() else 0,
                    'sportId': 1,
                    'odds': {
                        'home': home_odds,
                        'draw': draw_odds,
                        'away': away_odds
                    }
                })
            except: continue
    except Exception as e:
        log_msg(f"[ERROR] Soccer24 Fetch: {e}")
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    log_msg(f"[DEBUG] Soccer24 Parsed Matches: {len(matches)}")
    return matches


    log_msg(f"[DEBUG] Soccer24 Parsed Matches: {len(matches)}")
    return matches

# --- Sofascore Scraper (Table Tennis) ---
def fetch_sofascore_table_tennis(page):
    log_msg("[DEBUG] fetch_sofascore_table_tennis: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    # 1. Fetch Live List
    list_url = "https://www.sofascore.com/api/v1/sport/table-tennis/events/live"
    matches = []
    
    try:
        # We use goto with JSON response interception manually or just expect JSON on page
        # Getting JSON via page.goto works if the browser renders it (which Chrome does) -> innerText
        # BUT explicitly waiting for the response is cleaner.
        # Let's use the direct response extraction
        
        response = page.goto(list_url, timeout=60000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[ERROR] Sofascore list fetch failed: {response.status}")
            return None
            
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
                        o_resp = page.goto(odds_url, timeout=60000, wait_until='domcontentloaded')
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    log_msg(f"[DEBUG] Sofascore TT: Parsed {len(matches)} matches.")
    return matches

# --- Sofascore Scraper (Esports) ---
def fetch_sofascore_esports(page):
    log_msg("[DEBUG] fetch_sofascore_esports: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    list_url = "https://www.sofascore.com/api/v1/sport/esports/events/live"
    matches = []
    
    try:
        response = page.goto(list_url, timeout=60000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[ERROR] Sofascore Esports list fetch failed: {response.status}")
            return None
            
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
                
                # ALWAYS try vote-based odds first (most reliable for esports since Sofascore API returns 404)
                vote = ev.get('vote', {})
                vote_home = vote.get('vote1', 0)
                vote_away = vote.get('vote2', 0)
                if vote_home > 0 and vote_away > 0:
                    try:
                        total = vote_home + vote_away
                        odds_data['home'] = round(total / vote_home, 2)
                        odds_data['away'] = round(total / vote_away, 2)
                        log_msg(f"[DEBUG] Esports {mid}: Derived odds from votes H={odds_data['home']} A={odds_data['away']}")
                    except: pass
                
                # If no vote data, try the odds API (usually returns 404 for esports, but worth trying)
                if not odds_data['home'] and i < 10:  # Reduced from 20 to 10 to save time
                    time.sleep(0.3)  # Shorter delay
                    odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                    try:
                        o_resp = page.goto(odds_url, timeout=15000)  # Reduced timeout
                        if o_resp and o_resp.ok:
                            o_json = o_resp.json()
                            markets = o_json.get('markets', [])
                            
                            for m in markets:
                                market_name = m.get('marketName', '')
                                is_main = m.get('isMain', False)
                                
                                if is_main or market_name in ['Winner', 'Match Winner', 'Full time', 'Map 1 Winner', 'To Win Match', 'Money Line']:
                                    choices = m.get('choices', [])
                                    if len(choices) >= 2:
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
                                            log_msg(f"[DEBUG] Esports {mid}: Found API odds H={home_val} A={away_val}")
                                            break
                    except Exception as e:
                        pass  # Expected for esports - API returns 404
                
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    return matches

# --- Sofascore Scraper (Football) ---
def fetch_sofascore_football(page):
    log_msg("[DEBUG] fetch_sofascore_football: Entry")
    if page.is_closed(): raise Exception("Browser closed")
    
    url = "https://www.sofascore.com/api/v1/sport/football/events/live"
    matches = []
    
    try:
        response = page.goto(url, timeout=45000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[WARN] Sofascore Football fetch failed: {response.status}")
            return None
            
        try:
            data = response.json()
        except:
            text = page.locator("body").inner_text()
            data = json.loads(text)
            
        events = data.get('events', [])
        log_msg(f"[DEBUG] Sofascore Football: Found {len(events)} events")
        
        for ev in events:
            try:
                mid = str(ev.get('id'))
                home = ev.get('homeTeam', {}).get('name', 'Unknown')
                away = ev.get('awayTeam', {}).get('name', 'Unknown')
                
                h_score = str(ev.get('homeScore', {}).get('current', 0))
                a_score = str(ev.get('awayScore', {}).get('current', 0))
                status_desc = ev.get('status', {}).get('description', 'Live')
                
                # Odds
                odds_data = {'home': None, 'away': None, 'draw': None}
                # Try simple vote approximation first
                vote = ev.get('vote', {})
                v1 = vote.get('vote1', 0)
                vx = vote.get('voteX', 0)
                v2 = vote.get('vote2', 0)
                
                if v1+vx+v2 > 50: # Only if enough votes
                    total = v1+vx+v2
                    try:
                        odds_data['home'] = round(total/v1, 2) if v1 else None
                        odds_data['draw'] = round(total/vx, 2) if vx else None
                        odds_data['away'] = round(total/v2, 2) if v2 else None
                    except: pass

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
                    'sportId': 1, # Football
                    'odds': odds_data,
                    'match_data_extra': ev
                })
            except Exception as e:
                continue
                
    except Exception as e:
        log_msg(f"[ERROR] Sofascore Football Fetch: {e}")
        if "browser" in str(e).lower(): raise e
        return None
        
    return matches

# --- Sofascore Scraper (Basketball) ---
def fetch_sofascore_basketball(page):
    log_msg("[DEBUG] fetch_sofascore_basketball: Entry")
    if page.is_closed(): raise Exception("Browser closed")
    
    url = "https://www.sofascore.com/api/v1/sport/basketball/events/live"
    matches = []
    
    try:
        response = page.goto(url, timeout=45000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[WARN] Sofascore Basketball fetch failed: {response.status}")
            return None
            
        try:
            data = response.json()
        except:
            text = page.locator("body").inner_text()
            data = json.loads(text)
            
        events = data.get('events', [])
        log_msg(f"[DEBUG] Sofascore Basketball: Found {len(events)} events")
        
        for ev in events:
            try:
                mid = str(ev.get('id'))
                home = ev.get('homeTeam', {}).get('name', 'Unknown')
                away = ev.get('awayTeam', {}).get('name', 'Unknown')
                
                h_score = str(ev.get('homeScore', {}).get('current', 0))
                a_score = str(ev.get('awayScore', {}).get('current', 0))
                status_desc = ev.get('status', {}).get('description', 'Live')
                
                # Odds
                odds_data = {'home': None, 'away': None, 'draw': None}
                # Try simple vote approximation
                vote = ev.get('vote', {})
                v1 = vote.get('vote1', 0)
                v2 = vote.get('vote2', 0)
                if v1+v2 > 20:
                    total = v1+v2
                    try:
                        odds_data['home'] = round(total/v1, 2) if v1 else None
                        odds_data['away'] = round(total/v2, 2) if v2 else None
                    except: pass
                    
                matches.append({
                    'id': f"sfb_{mid}",
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
                    'sportId': 3, # Basketball
                    'odds': odds_data,
                    'match_data_extra': ev
                })
            except: continue
                
    except Exception as e:
        log_msg(f"[ERROR] Sofascore Basketball Fetch: {e}")
        if "browser" in str(e).lower(): raise e
        return None
        
    return matches

def fetch_sofascore_volleyball(page):
    log_msg("[DEBUG] fetch_sofascore_volleyball: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    list_url = "https://www.sofascore.com/api/v1/sport/volleyball/events/live"
    matches = []
    
    try:
        response = page.goto(list_url, timeout=60000, wait_until='domcontentloaded')
        if not response.ok:
            log_msg(f"[ERROR] Sofascore Volleyball list fetch failed: {response.status}")
            return None
            
        try:
            data = response.json()
        except:
            text = page.locator("body").inner_text()
            data = json.loads(text)
            
        events = data.get('events', [])
        log_msg(f"[DEBUG] Sofascore Volleyball: Found {len(events)} live events.")
        
        for i, ev in enumerate(events):
            try:
                mid = str(ev.get('id'))
                home = ev.get('homeTeam', {}).get('name', 'Unknown')
                away = ev.get('awayTeam', {}).get('name', 'Unknown')
                
                h_score = str(ev.get('homeScore', {}).get('current', 0))
                a_score = str(ev.get('awayScore', {}).get('current', 0))
                status_desc = ev.get('status', {}).get('description', 'Live')
                
                odds_data = {'home': None, 'away': None, 'draw': None}
                
                # Try vote-based odds first (fallback for sparse odds data)
                vote = ev.get('vote', {})
                vote_home = vote.get('vote1', 0)
                vote_away = vote.get('vote2', 0)
                if vote_home > 0 and vote_away > 0:
                    try:
                        total = vote_home + vote_away
                        odds_data['home'] = round(total / vote_home, 2)
                        odds_data['away'] = round(total / vote_away, 2)
                    except: pass
                
                # Try API if no vote data
                if not odds_data['home'] and i < 15:
                    time.sleep(0.3)
                    odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                    try:
                        o_resp = page.goto(odds_url, timeout=15000)
                        if o_resp and o_resp.ok:
                            o_json = o_resp.json()
                            markets = o_json.get('markets', [])
                            for m in markets:
                                if m.get('isMain') or m.get('marketName') in ['Winner', 'Match Winner', 'Full time']:
                                    choices = m.get('choices', [])
                                    if len(choices) >= 2:
                                        def parse_frac(s):
                                            if '/' in str(s):
                                                n, d = str(s).split('/')
                                                return round(1 + int(n)/int(d), 2)
                                            return s
                                        odds_data['home'] = str(parse_frac(choices[0].get('fractionalValue', choices[0].get('decimalValue'))))
                                        odds_data['away'] = str(parse_frac(choices[1].get('fractionalValue', choices[1].get('decimalValue'))))
                                        break
                    except:
                        pass
                
                matches.append({
                    'id': f"sfv_{mid}",
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
                    'sportId': 13,
                    'odds': odds_data,
                    'match_data_extra': ev
                })
            except:
                continue
                
    except Exception as e:
        log_msg(f"[ERROR] Sofascore Volleyball Fetch: {e}")
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    log_msg(f"[DEBUG] Sofascore Volleyball: Parsed {len(matches)} matches.")
    return matches

# -------------------------------------------------------------------
# Cricket - Sofascore (Fallback/Redundancy)
# -------------------------------------------------------------------
def fetch_sofascore_cricket(page):
    log_msg("[DEBUG] fetch_sofascore_cricket: Entry")
    matches = []
    
    # URL for Live Cricket Events
    list_url = "https://www.sofascore.com/api/v1/sport/cricket/events/live"
    
    try:
        # Navigate to API endpoint directly
        log_msg(f"[DEBUG] fetch_sofascore_cricket: Navigating to {list_url}")
        try:
            # We use a known working page to get valid context, then fetch API
            resp = page.goto(list_url, wait_until='networkidle', timeout=30000)
            if not resp.ok:
                 log_msg(f"[WARN] fetch_sofascore_cricket: API returned {resp.status}")
                 return []
        except Exception as e:
            log_msg(f"[WARN] fetch_sofascore_cricket: Navigation failed: {e}")
            return []

        # Extract JSON from body
        try:
            content = page.inner_text("body")
            data = json.loads(content)
            events = data.get('events', [])
            log_msg(f"[DEBUG] fetch_sofascore_cricket: Found {len(events)} events in JSON")
        except Exception as e:
            log_msg(f"[WARN] fetch_sofascore_cricket: Failed to parse JSON: {e}")
            return []

        for evt in events:
            try:
                mid = str(evt.get('id'))
                status_type = evt.get('status', {}).get('type')
                
                # Only process live/inprogress
                if status_type != 'inprogress':
                    continue

                home = evt.get('homeTeam', {})
                away = evt.get('awayTeam', {})
                
                # Scores
                home_score_obj = evt.get('homeScore', {})
                away_score_obj = evt.get('awayScore', {})
                
                def fmt_score(sc_obj):
                    if not sc_obj: return "0"
                    curr = sc_obj.get('current', 0)
                    inngs = sc_obj.get('innings', {})
                    # Try to find latest inning
                    last_inn = list(inngs.values())[-1] if inngs else {}
                    
                    wickets = last_inn.get('wickets', 0)
                    overs = last_inn.get('overs', 0)
                    runs = last_inn.get('score', 0)
                    
                    return f"{runs}/{wickets} ({overs})"

                home_sc = fmt_score(home_score_obj)
                away_sc = fmt_score(away_score_obj)
                
                # Times
                match_time = "Live"
                
                # Construct Match Object
                m = {
                    'id': f"sofa_{mid}",
                    'sportId': 2, # Cricket ID in sportsdb
                    'competition': evt.get('tournament', {}).get('name', 'Unknown'),
                    'homeTeam': home.get('name', 'Unknown'),
                    'awayTeam': away.get('name', 'Unknown'),
                    'times': match_time,
                    'matchTime': match_time,
                    'statusId': 2, 
                    'matchStatus': 'Live',
                    'venue': '',
                    'referee': '',
                    'home_name_resolved': home.get('name'),
                    'away_name_resolved': away.get('name'),
                    'ext': {
                        'home_score': home_sc,
                        'away_score': away_sc,
                        'source': 'sofascore',
                        'raw_id': mid
                    }
                }
                matches.append(m)

            except Exception as e:
                log_msg(f"[WARN] fetch_sofascore_cricket: Error parsing event: {e}")
                continue

    except Exception as e:
        log_msg(f"[ERROR] fetch_sofascore_cricket: Top level error: {e}")
    
    log_msg(f"[DEBUG] fetch_sofascore_cricket: Returning {len(matches)} matches")
    return matches

def fetch_cricket_session_odds(page, match_name):
    """
    Placeholder for fetching Session/Lambi odds.
    Requires a valid source (e.g. Betting Site or Premium API).
    Returns dict: {'6_over': ..., 'lambi': ...}
    """
    # TODO: Implement scraping for CREX or Exchange
    return {}

# -------------------------------------------------------------------
# Sofascore Scraper (Motorsport - F1, MotoGP, NASCAR, etc.)
# -------------------------------------------------------------------
def fetch_sofascore_motorsport(page):
    """
    Fetches motorsport events from SofaScore including:
    - Formula 1 (F1)
    - MotoGP
    - NASCAR
    - Formula E
    - IndyCar
    - WRC (World Rally Championship)
    
    Fetches both live AND upcoming events for season coverage.
    """
    log_msg("[DEBUG] fetch_sofascore_motorsport: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    matches = []
    
    # Motorsport categories to fetch
    motorsport_urls = [
        ("https://www.sofascore.com/api/v1/sport/motorsport/events/live", "live"),
        ("https://www.sofascore.com/api/v1/sport/motorsport/scheduled-events/next", "upcoming"),
    ]
    
    for url, event_type in motorsport_urls:
        try:
            response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
            if not response.ok:
                log_msg(f"[WARN] Sofascore Motorsport {event_type} fetch failed: {response.status}")
                continue
                
            try:
                data = response.json()
            except:
                text = page.locator("body").inner_text()
                data = json.loads(text)
                
            events = data.get('events', [])
            log_msg(f"[DEBUG] Sofascore Motorsport ({event_type}): Found {len(events)} events.")
            
            for i, ev in enumerate(events):
                try:
                    mid = str(ev.get('id'))
                    
                    # For motorsport, home/away represent different things
                    # Usually it's the event name or driver/team
                    home_team = ev.get('homeTeam', {})
                    away_team = ev.get('awayTeam', {})
                    
                    # Get tournament/series info (F1, MotoGP, etc.)
                    tournament = ev.get('tournament', {})
                    series_name = tournament.get('name', 'Motorsport')
                    category = tournament.get('category', {}).get('name', '')
                    
                    # Event name construction
                    if home_team.get('name') and away_team.get('name'):
                        event_name = f"{home_team.get('name')} vs {away_team.get('name')}"
                        home = home_team.get('name', 'Unknown')
                        away = away_team.get('name', series_name)
                    else:
                        # Single event format (races, etc.)
                        event_name = ev.get('slug', '').replace('-', ' ').title()
                        home = series_name
                        away = category or event_name
                    
                    # Scores/Results
                    h_score = str(ev.get('homeScore', {}).get('current', 0))
                    a_score = str(ev.get('awayScore', {}).get('current', 0))
                    
                    # Status
                    status_obj = ev.get('status', {})
                    status_desc = status_obj.get('description', 'Scheduled')
                    status_type = status_obj.get('type', 'notstarted')
                    
                    is_live = status_type in ['inprogress', 'live']
                    
                    # Start time for upcoming events
                    start_timestamp = ev.get('startTimestamp', 0)
                    
                    # Odds (motorsport odds are rare but try to fetch)
                    odds_data = {'home': None, 'away': None, 'draw': None}
                    if i < 10 and event_type == 'live':
                        time.sleep(0.3)
                        try:
                            odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                            o_resp = page.goto(odds_url, timeout=30000)
                            if o_resp and o_resp.ok:
                                o_json = o_resp.json()
                                markets = o_json.get('markets', [])
                                for m in markets:
                                    if m.get('isMain') or 'winner' in m.get('marketName', '').lower():
                                        choices = m.get('choices', [])
                                        if len(choices) >= 2:
                                            odds_data['home'] = choices[0].get('decimalValue') or choices[0].get('fractionalValue')
                                            odds_data['away'] = choices[1].get('decimalValue') or choices[1].get('fractionalValue')
                                            break
                        except:
                            pass
                    
                    matches.append({
                        'id': f"sfm_{mid}",
                        'matchStatus': 2 if is_live else 1,
                        'statusId': 2 if is_live else 1,
                        'is_live_override': is_live,
                        'status_text_override': status_desc,
                        'homeTeam': {'name': home},
                        'awayTeam': {'name': away},
                        'home_name_resolved': home,
                        'away_name_resolved': away,
                        'homeScore': h_score,
                        'awayScore': a_score,
                        'sportId': 99,  # Motorsport ID
                        'odds': odds_data,
                        'match_data_extra': {
                            'series': series_name,
                            'category': category,
                            'event_type': event_type,
                            'start_timestamp': start_timestamp,
                            'full_event': ev
                        }
                    })
                except Exception as e:
                    log_msg(f"[WARN] Motorsport parse error: {e}")
                    continue
                    
        except Exception as e:
            log_msg(f"[ERROR] Sofascore Motorsport ({event_type}) Fetch: {e}")
            if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
                raise e
    
    log_msg(f"[DEBUG] Sofascore Motorsport: Parsed {len(matches)} total events.")
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
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    matches = []
    
    try:
        # Set random user agent
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        
        # Random delay before request
        time.sleep(random.uniform(1.0, 2.5))
        
        # FlashScore Ice Hockey live page
        url = "https://www.flashscore.com/ice-hockey/"
        response = page.goto(url, timeout=60000, wait_until='networkidle')
        
        if not response.ok:
            log_msg(f"[ERROR] FlashScore Ice Hockey fetch failed: {response.status}")
            return None
        
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    return matches


# --- OddsPortal Scraper (Optimized) ---

def fetch_oddsportal_hockey(page):
    """Fetches Ice Hockey odds from OddsPortal with optimized wait strategies."""
    log_msg("[DEBUG] fetch_oddsportal_hockey: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        # Try Live page first
        url = "https://www.oddsportal.com/hockey/live/"
        response = page.goto(url, timeout=60000, wait_until='domcontentloaded') # Relaxed wait
        
        if not response or not response.ok:
            log_msg(f"[ERROR] OddsPortal Hockey fetch failed: {response.status if response else 'No Response'}")
            return None
        
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    return matches


def fetch_oddsportal_esports(page):
    """Fetches Esports odds from OddsPortal with optimized wait strategies."""
    log_msg("[DEBUG] fetch_oddsportal_esports: Entry")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        url = "https://www.oddsportal.com/esports/live/"
        response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
        
        if not response or not response.ok:
             log_msg(f"[ERROR] OddsPortal Esports fetch failed: {response.status if response else 'No Resp'}")
             return None
        
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    return matches

def fetch_oddsportal_generic(page, sport_slug, sport_db_id):
    """Fetches odds for Generic sports (Volleyball, Handball, etc) from OddsPortal."""
    log_msg(f"[DEBUG] fetch_oddsportal_generic: Entry for {sport_slug}")
    if page.is_closed(): raise Exception("Target page, context or browser has been closed")
    matches = []
    
    try:
        page.set_extra_http_headers({"User-Agent": get_random_ua()})
        time.sleep(random.uniform(1.0, 2.0))
        
        url = f"https://www.oddsportal.com/{sport_slug}/live/"
        response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
        
        if not response or not response.ok:
             return None
        
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
        if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
            raise e
        return None
        
    return matches



def worker_loop(worker_name, assigned_sports, cycle_sleep=10):
    global SHUTDOWN_FLAG
    log_msg(f"[{worker_name}] Starting Worker Loop...")
    conn = None
    browser = None
    p = None
    
    while not SHUTDOWN_FLAG:
        # Update Heartbeat
        SCRAPER_STATS['workers'][worker_name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # 1. Initialize Resources per Thread
            if not conn or conn.closed:
                conn = initialize_db()
                if not conn:
                    log_msg(f"[{worker_name}] DB Connection failed. Retrying in 10s...")
                    time.sleep(10)
                    continue
            
            if not browser:
                # Create a new Playwright instance for this thread
                from playwright.sync_api import sync_playwright
                p = sync_playwright().start()
                
                # Browser launch args - Enhanced for Railway/Docker environments
                launch_args = [
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-gpu', 
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--exclude-switches=enable-automation',
                    '--use-fake-ui-for-media-stream',
                    '--disable-notifications',
                    '--disable-extensions',
                    # Railway/Docker specific fixes
                    # '--single-process', # CAUSES CRASHES ON NEWER CHROMIUM
                    '--disable-setuid-sandbox',
                    '--disable-software-rasterizer',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--metrics-recording-only',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                ]
                
                # Configure proxy if enabled
                proxy_settings = None
                if USE_PROXY:
                    proxy_settings = {
                        'server': PROXY_CONFIG['server'],
                        'username': PROXY_CONFIG['username'],
                        'password': PROXY_CONFIG['password']
                    }
                    log_msg(f"[{worker_name}] Using DataImpulse rotating proxy: {PROXY_CONFIG['server']}")
                
                browser = p.chromium.launch(
                    headless=True,
                    args=launch_args,
                    proxy=proxy_settings
                )
            
            # Generate Random UA
            ua = UserAgent(browsers=['chrome', 'edge'])
            random_ua = ua.random
            
            # Contexts with proxy authentication
            context_options_desktop = {
                'user_agent': random_ua,
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'en-US',
                'timezone_id': 'America/New_York'
            }
            if USE_PROXY:
                context_options_desktop['proxy'] = {
                    'server': PROXY_CONFIG['server'],
                    'username': PROXY_CONFIG['username'],
                    'password': PROXY_CONFIG['password']
                }
            
            context_desktop = browser.new_context(**context_options_desktop)
            # Use Playwright Stealth instead of manual scripts
            page_desktop = context_desktop.new_page()
            stealth_sync(page_desktop)
            
            # Mobile context with proxy
            iphone = p.devices['iPhone 12']
            context_options_mobile = {**iphone}
            # Mobile UA acts differently, let's keep default device UA but add stealth scripts
            
            if USE_PROXY:
                context_options_mobile['proxy'] = {
                    'server': PROXY_CONFIG['server'],
                    'username': PROXY_CONFIG['username'],
                    'password': PROXY_CONFIG['password']
                }
            context_mobile = browser.new_context(**context_options_mobile)
            # Use Playwright Stealth
            page_mobile = context_mobile.new_page()
            stealth_sync(page_mobile)

            log_msg(f"[{worker_name}] Browser Ready (Proxy: {USE_PROXY}). Processing: {assigned_sports}")
            
            # Inner Loop for Stability (re-use browser)
            cycle_count = 0
            max_cycles = 20 # Restart browser every 20 cycles to prevent leaks
            
            while cycle_count < max_cycles and not SHUTDOWN_FLAG:
                # Update Heartbeat (Inner Loop)
                SCRAPER_STATS['workers'][worker_name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                start_time = time.time()
                
                # Check Commands (Only Main Thread - optional, or shared?)
                # For simplicity, Thread 1 handles commands if assigned_sports has football
                if 'football' in assigned_sports:
                    try:
                        while not COMMAND_QUEUE.empty():
                            cmd = COMMAND_QUEUE.get_nowait()
                            log_msg(f"[{worker_name}] Processing command: {cmd}")
                            # FORCE_REFRESH logic could go here
                    except: pass

                if conn.closed: raise Exception("DB Conn Closed")

                for sport in assigned_sports:
                    if sport not in SPORTS_CONFIG: continue
                    config = SPORTS_CONFIG[sport]
                    
                    # Track which source this sport uses for blocking tracker
                    source_name = None
                    browser_crashed = False
                    
                    try:
                        matches = []
                        # Routing 
                        if sport == 'football':
                            source_name = 'sofascore'
                            log_msg(f"[{worker_name}] Fetching football (Sofascore)...")
                            matches = fetch_sofascore_football(page_mobile)
                        elif sport == 'basketball':
                            source_name = 'sofascore'
                            log_msg(f"[{worker_name}] Fetching basketball (Sofascore)...")
                            matches = fetch_sofascore_basketball(page_mobile)
                        elif sport == 'table-tennis':
                            source_name = 'sofascore'
                            log_msg(f"[{worker_name}] Fetching table-tennis...")
                            matches = fetch_sofascore_table_tennis(page_mobile)
                        elif sport == 'esports':
                            source_name = 'sofascore'
                            log_msg(f"[{worker_name}] Fetching esports...")
                            matches = fetch_sofascore_esports(page_mobile)
                            # OddsPortal backup
                            op_matches = fetch_oddsportal_esports(page_desktop)
                            if op_matches:
                                record_source_success('oddsportal')
                                for m in matches:
                                    if not m.get('odds', {}).get('home'):
                                        for op in op_matches:
                                            if (m['home_name_resolved'].lower() in op['home_name_resolved'].lower() or 
                                                op['home_name_resolved'].lower() in m['home_name_resolved'].lower()):
                                                m['odds'] = op['odds']
                                                break
                        elif sport == 'ice-hockey':
                            source_name = 'aiscore'
                            log_msg(f"[{worker_name}] Fetching ice-hockey...")
                            matches = fetch_aiscore_live(page_mobile, config['slug'], config['state_key'])
                            op_hockey = fetch_oddsportal_hockey(page_desktop)
                            if op_hockey:
                                record_source_success('oddsportal')
                                for m in matches:
                                    if not m.get('odds', {}).get('home'):
                                        for op in op_hockey:
                                            if (m['home_name_resolved'].lower() in op['home_name_resolved'].lower() or 
                                                op['home_name_resolved'].lower() in m['home_name_resolved'].lower()):
                                                m['odds'] = op['odds']
                                                break
                        
                        # Minor Sports (OddsPortal)
                        elif sport == 'volleyball':
                             source_name = 'sofascore'
                             log_msg(f"[{worker_name}] Fetching volleyball (SofaScore)...")
                             matches = fetch_sofascore_volleyball(page_mobile)
                        elif sport == 'motorsport':
                             source_name = 'sofascore'
                             log_msg(f"[{worker_name}] Fetching motorsport (SofaScore)...")
                             matches = fetch_sofascore_motorsport(page_mobile)
                             log_msg(f"[{worker_name}] Fetching motorsport (SofaScore)...")
                             matches = fetch_sofascore_motorsport(page_mobile)
                        elif sport == 'cricket':
                             source_name = 'aiscore'
                             log_msg(f"[{worker_name}] Fetching cricket (AiScore)...")
                             matches = fetch_aiscore_live(page_mobile, config['slug'], config['state_key'])
                             
                             if not matches:
                                 log_msg(f"[{worker_name}] AiScore returned 0/None for Cricket. Trying Sofascore Fallback...")
                                 sofa_matches = fetch_sofascore_cricket(page_mobile)
                                 if sofa_matches:
                                     matches = sofa_matches
                                     source_name = 'sofascore'
                                     log_msg(f"[{worker_name}] Switched to Sofascore (Fallback Success).")
                        elif sport in ['handball', 'baseball', 'snooker', 'rugby', 'water-polo']:
                             source_name = 'oddsportal'
                             log_msg(f"[{worker_name}] Fetching {sport} (OddsPortal)...")
                             # Map sport to ID/Slug manually or use generic
                             slugs = {
                                 'handball': 'handball', 'baseball': 'baseball',
                                 'snooker': 'snooker', 'rugby': 'rugby-league', 'water-polo': 'water-polo'
                             }
                             ids = {
                                 'handball': 6, 'baseball': 3,
                                 'snooker': 14, 'rugby': 12, 'water-polo': 15
                             }
                             matches = fetch_oddsportal_generic(page_desktop, slugs.get(sport, sport), ids.get(sport, 1))
                             
                        else:
                            # Generic AiScore (Cricket, Badminton, AmFootball)
                            source_name = 'aiscore'
                            log_msg(f"[{worker_name}] Fetching {sport} (AiScore)...")
                            matches = fetch_aiscore_live(page_mobile, config['slug'], config['state_key'])

                        if matches is None:
                            # Fetch returned None = failure
                            log_msg(f"[{worker_name}] Skipping sync for {sport} due to fetch failure.")
                            if source_name:
                                record_source_failure(source_name, f"Returned None for {sport}")
                            continue

                        # Fetch succeeded - record success
                        if source_name:
                            record_source_success(source_name)

                        if matches:
                            log_msg(f"[{worker_name}] Upserting {len(matches)} for {sport}")
                            active_ids = upsert_matches(conn, sport, matches)
                            cleanup_stale_matches(conn, sport, active_ids)
                        else:
                            # Empty list = successful fetch, but 0 matches
                            log_msg(f"[{worker_name}] No live matches found for {sport}. Running cleanup.")
                            cleanup_stale_matches(conn, sport, [])
                            
                            # CRITICAL FIX: Update last_sync even if 0 matches found, 
                            # because the fetch was successful (just empty).
                            if sport not in SCRAPER_STATS['sports']:
                                SCRAPER_STATS['sports'][sport] = {}
                            SCRAPER_STATS['sports'][sport]['last_sync'] = str(datetime.now())
                            SCRAPER_STATS['sports'][sport]['matches'] = 0
                            
                    except Exception as e:
                        log_msg(f"[{worker_name}] [ERROR] {sport}: {e}")
                        
                        # Record failure in blocking tracker
                        if source_name:
                            record_source_failure(source_name, str(e))
                        
                        # CRITICAL: Detect browser closed error and force IMMEDIATE restart
                        err_str = str(e).lower()
                        if "target page, context or browser has been closed" in err_str or "browser has been closed" in err_str or "page.goto" in err_str:
                            log_msg(f"[{worker_name}] [CRITICAL] Browser died. Forcing immediate restart...")
                            browser_crashed = True
                             
                        if "cloudflare blocked" in err_str or "just a moment" in err_str:
                            log_msg(f"[{worker_name}] [CRITICAL] Cloudflare Block Detected. Forcing immediate restart...")
                            browser_crashed = True
                        
                        # IMPORTANT: Break out of sports loop immediately on crash
                        if browser_crashed:
                            cycle_count = max_cycles + 5  # Force exit inner cycle loop too
                            break
                        # Don't break loop for minor errors, continue to next sport
                
                # Heartbeat log for monitoring
                if cycle_count % 5 == 0:
                    log_msg(f"[{worker_name}] [HEARTBEAT] Alive - Cycle {cycle_count}/{max_cycles}")
                
                elapsed = time.time() - start_time
                wait = max(5.0, cycle_sleep - elapsed)
                time.sleep(wait)
                cycle_count += 1
            
            # End of Cycle - Refresh Browser
            log_msg(f"[{worker_name}] Cycling Browser Refresh...")
            browser.close()
            p.stop()
            browser = None
            
        except Exception as e:
            log_msg(f"[{worker_name}] [CRASH]: {e}")
            time.sleep(10)
            try:
                if browser: browser.close()
                if p: p.stop()
            except: pass
            browser = None

def watchdog_loop():
    """
    Monitors worker threads. If any thread hasn't updated its heartbeat 
    in > 600 seconds (10 mins), kill the process to force a restart.
    """
    log_msg("[WATCHDOG] Started. Monitoring workers...")
    time.sleep(60) # Startup grace period
    
    while not SHUTDOWN_FLAG:
        try:
            now = datetime.now()
            workers = SCRAPER_STATS.get('workers', {})
            
            for w_name, last_beat in workers.items():
                # Parse timestamp if string
                if isinstance(last_beat, str):
                    try: dt = datetime.strptime(last_beat, "%Y-%m-%d %H:%M:%S")
                    except: continue
                else:
                    dt = last_beat
                
                delta = (now - dt).total_seconds()
                
                # Check for critical staleness (10 minutes)
                if delta > 600:
                    log_msg(f"[WATCHDOG] CRITICAL: Worker '{w_name}' blocked for {int(delta)}s. Forcing restart!")
                    # Force exit - Docker/Railway will restart us
                    os._exit(1)
            
            time.sleep(30) # Check every 30s
            
        except Exception as e:
            log_msg(f"[WATCHDOG] Error: {e}")
            time.sleep(30)

def run_scraper():
    log_msg("[SUPERVISOR] Starting Multi-Threaded Scraper...")

    # Start Watchdog
    t_watch = threading.Thread(target=watchdog_loop, daemon=True)
    t_watch.start()
    
    # Start Telegram Alert Monitor
    t_monitor = threading.Thread(target=monitor_db_freshness, daemon=True)
    t_monitor.start()
    
    # Group 0: Critical (Cricket)
    g0 = ['cricket']

    # Group 1: High Priority / High Volume (Fast)
    g1 = ['football', 'basketball', 'tennis']
    
    # Group 2: Mid Priority (SofaScore)
    g2 = ['table-tennis', 'esports', 'volleyball', 'motorsport']
    
    # Group 3: Low Priority / Slow / OddsPortal (Likely to timeout)
    g3 = ['ice-hockey', 'handball', 'baseball', 'snooker', 'rugby', 'water-polo', 'badminton', 'amfootball']
    
    t0 = threading.Thread(target=worker_loop, args=("T0-Cricket", g0, 10)) # 10s cycle
    t1 = threading.Thread(target=worker_loop, args=("T1-Main", g1, 15)) # 15s cycle
    t2 = threading.Thread(target=worker_loop, args=("T2-Sofa", g2, 20)) # 20s cycle
    t3 = threading.Thread(target=worker_loop, args=("T3-Minor", g3, 60)) # 60s cycle (slower)
    
    t0.start()
    t1.start()
    t2.start()
    t3.start()
    
    t0.join()
    t1.join()
    t2.join()
    t3.join()


if __name__ == "__main__":
    # Start web server thread
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    
    # Run main scraper (blocking)
    run_scraper()
