
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_odds_fixed(match):
    """
    Simulating the fixed logic
    """
    odds = {'home': None, 'away': None, 'draw': None}
    
    if 'odds' in match and isinstance(match['odds'], dict):
        return match['odds']
    
    try:
        # FIXED LOGIC: Handle None explicitly
        ext = match.get('ext') or {}
        odds_data = ext.get('odds') or {}
        odd_items = odds_data.get('oddItems') or []
        
        print(f"DEBUG: Found {len(odd_items)} oddItems")
        if len(odd_items) > 1 and odd_items[1]:
            odd_arr = odd_items[1].get('odd', [])
            print(f"DEBUG: odd_arr: {odd_arr}")
            if len(odd_arr) >= 3:
                odds['home'] = odd_arr[0] if odd_arr[0] and odd_arr[0] != '0' else None
                odds['away'] = odd_arr[2] if odd_arr[2] and odd_arr[2] != '0' else None
                if len(odd_arr) > 1 and odd_arr[1] and odd_arr[1] != '0':
                    odds['draw'] = odd_arr[1]
    except Exception as e:
        print(f"DEBUG Error: {e}")
        pass
        
    return odds

def debug_basketball_fix():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        print("Checking live_basketball again...")
        # Get the same problematic row
        cur.execute("SELECT match_id, last_updated, match_data FROM live_basketball ORDER BY last_updated DESC LIMIT 1")
        row = cur.fetchone()
        
        if row:
            mid, updated, data = row
            print(f"Match ID: {mid}")
            
            # Test extraction with FIX
            raw_odds = get_odds_fixed(data)
            print(f"Extracted Odds (Fixed): {raw_odds}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_basketball_fix()
