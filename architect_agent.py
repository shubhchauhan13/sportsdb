
import psycopg2
import time
import requests
import os
from datetime import datetime
import json

# OpenRouter Config
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"  # More available free model
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# DB Config
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
SCRAPER_API = "http://localhost:8080"

def call_openrouter(prompt):
    """Calls OpenRouter API with the given prompt."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",  # Required by OpenRouter
        "X-Title": "SportsDB Architect Agent"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    
    try:
        log(f" -> 🤖 Calling OpenRouter ({OPENROUTER_MODEL})...")
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 429:
            log(f" -> ⚠️ OpenRouter 429: {response.text[:200]}")
            raise Exception("429 Rate Limit")
            
        response.raise_for_status()
        data = response.json()
        
        if 'choices' in data and len(data['choices']) > 0:
            result = data['choices'][0]['message']['content'].strip()
            log(f" -> ✅ AI Response received ({len(result)} chars)")
            return result
        else:
            log(f" -> ⚠️ Unexpected response: {data}")
            return None
            
    except requests.exceptions.HTTPError as e:
        log(f"OpenRouter HTTP Error: {response.status_code} - {response.text[:300]}")
        return None
    except Exception as e:
        if "429" in str(e):
            raise e
        log(f"OpenRouter Error: {e}")
        return None

def ask_gemini_diagnose_old(match_data_dump):
    """DEPRECATED - Old Google AI function."""
    return None

def log(msg):
    print(f"[ARCHITECT] {msg}")

def get_conn():
    return psycopg2.connect(DB_CONNECTION_STRING)

# --- Monitors ---

ALL_TABLES = [
    'live_football', 'live_basketball', 'live_tennis', 'live_table_tennis', 
    'live_esports', 'live_cricket', 'live_ice_hockey', 'live_baseball',
    'live_volleyball', 'live_handball', 'live_rugby', 'live_badminton'
]

def search_web_for_odds(home, away):
    """Searches the open web for match odds."""
    try:
        from duckduckgo_search import DDGS
        query = f"{home} vs {away} betting odds live"
        log(f" -> 🌍 Searching web: '{query}'")
        
        results_text = ""
        with DDGS() as ddgs:
            # Get up to 3 results to save tokens
            results = list(ddgs.text(query, max_results=3))
            for res in results:
                results_text += f"Title: {res['title']}\nSnippet: {res['body']}\nSource: {res['href']}\n\n"
        
        if not results_text:
            log(" -> 🌍 Web search found no results.")
            return None
            
        return results_text
    except ImportError:
        log(" -> ⚠️ duckduckgo-search not installed. Skipping web search.")
        return None
    except Exception as e:
        log(f" -> 🌍 Web Search Failed: {e}")
        return None

def check_missing_odds():
    """Finds LIVE matches with missing odds across ALL sports and attempts AI Fix (Internal + Web)."""
    conn = get_conn()
    cur = conn.cursor()
    
    total_found = 0
    
    for table_name in ALL_TABLES:
        try:
            # Select match_data 
            cur.execute(f"""
                SELECT match_id, home_team, away_team, match_data 
                FROM {table_name} 
                WHERE is_live = TRUE 
                AND (other_odds IS NULL OR other_odds->>'home' IS NULL OR other_odds->>'home' = 'None')
            """)
            rows = cur.fetchall()
            
            if rows:
                log(f"[{table_name}] Found {len(rows)} matches with missing odds.")
                total_found += len(rows)
                
                for r in rows:
                    mid = r[0]
                    home = r[1]
                    away = r[2]
                    m_data = r[3]
                    
                    log(f" -> Diagnosing {mid} ({home} vs {away}) with Gemini AI...")
                    
                    try:
                        ai_odds = None
                        
                        # 1. Try Web Search FIRST (no rate limits on DuckDuckGo)
                        log(" -> 🌍 Attempting Web Search first...")
                        search_dump = search_web_for_odds(home, away)
                        if search_dump:
                            ai_odds = ask_gemini_diagnose(search_dump, mode="web")
                        
                        # 2. If Web fails, Try Internal JSON as fallback
                        if not (ai_odds and (ai_odds.get('home') or ai_odds.get('away'))):
                            log(" -> Web empty. Trying Internal JSON...")
                            ai_odds = ask_gemini_diagnose(m_data, mode="json")

                        if ai_odds and (ai_odds.get('home') or ai_odds.get('away')):
                            home_odd = ai_odds.get('home', 'N/A')
                            away_odd = ai_odds.get('away', 'N/A')
                            log(f" ============================================")
                            log(f" 🎯 ODDS FIXED!")
                            log(f"    Match: {home} vs {away}")
                            log(f"    Table: {table_name}")
                            log(f"    Home Odds: {home_odd}")
                            log(f"    Away Odds: {away_odd}")
                            log(f" ============================================")
                            # SELF HEAL: Update the DB
                            try:
                                from psycopg2.extras import Json
                                cur.execute(f"UPDATE {table_name} SET other_odds = %s WHERE match_id = %s", (Json(ai_odds), mid))
                                conn.commit()
                                log(f" ✅ DB UPDATED: {mid}")
                            except Exception as e:
                                log(f" ❌ DB Update Failed: {e}")
                                conn.rollback()
                        else:
                            log(f" -> ❌ No odds found for: {home} vs {away}")
                        
                        # Rate limit protection: 20s delay between requests
                        time.sleep(20)
                        
                    except Exception as e:
                        if "429" in str(e):
                             log(f" -> Rate Limit Hit! Sleeping 60s...")
                             time.sleep(60)
                        else:
                             log(f" -> AI Error: {e}")

        except Exception as e:
            log(f"Error checking {table_name}: {e}")
            conn.rollback()
            
    if total_found == 0:
        log("No missing odds found in this cycle.")
            
    conn.close()

def ask_gemini_diagnose(data_input, mode="json"):
    """Uses OpenRouter (Gemini 2.0 Flash) to find hidden odds in data."""
    
    data_str = str(data_input)
    if len(data_str) > 8000: data_str = data_str[:8000]
    
    if mode == "json":
        prompt = f"""You are a Sports Data Archaeologist. Analyze this JSON for hidden odds keys ('winningOdds', 'vote', etc).
Return ONLY valid JSON: {{'home': float, 'away': float}} or null.
Data: {data_str}"""
    else: # Web Mode
        prompt = f"""You are a Sports Analyst. I have scraped search results for a match.
EXTRACT the current/live betting odds for Home and Away teams from the text snippets below.
Look for decimal (1.50) or fractional (1/2) odds.

Search Results:
{data_str}

Return ONLY valid JSON: {{'home': float, 'away': float}} or null.
If multiple sources differ, pick the most credible recent one."""
    
    try:
        text = call_openrouter(prompt)
        if not text:
            return None
            
        # clean code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
    except Exception as e:
        if "429" in str(e):
             raise e
        log(f"AI Error (mode={mode}): {e}")
        return None

def check_stuck_matches():
    """Finds LIVE matches not updated in > 10 mins."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT match_id, last_updated 
        FROM live_football 
        WHERE is_live = TRUE 
        AND last_updated < NOW() - INTERVAL '10 minutes'
    """)
    rows = cur.fetchall()
    
    if rows:
        log(f"Found {len(rows)} stuck Football matches.")
        for r in rows:
            mid = r[0]
            log(f" -> {mid} last updated: {r[1]}. Needs investigation.")
            
    conn.close()

# --- Main Loop ---

def run_architect():
    log("Architect Agent Online. Surveillance Active.")
    while True:
        try:
            check_missing_odds()
            check_stuck_matches()
        except Exception as e:
            log(f"Error in cycle: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    run_architect()
