
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_odds(match):
    """
    Copy of the function from scraper_service.py for testing
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
        print(f"DEBUG: Found {len(odd_items)} oddItems")
        if len(odd_items) > 1 and odd_items[1]:
            odd_arr = odd_items[1].get('odd', [])
            print(f"DEBUG: odd_arr: {odd_arr}")
            if len(odd_arr) >= 3:
                odds['home'] = odd_arr[0] if odd_arr[0] and odd_arr[0] != '0' else None
                odds['away'] = odd_arr[2] if odd_arr[2] and odd_arr[2] != '0' else None
                # Draw odds might be at index 1 for football
                if len(odd_arr) > 1 and odd_arr[1] and odd_arr[1] != '0':
                    odds['draw'] = odd_arr[1]
    except Exception as e:
        print(f"DEBUG Error: {e}")
        pass
        
    return odds

def debug_basketball():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        print("Checking live_basketball...")
        # Get one recent row
        cur.execute("SELECT match_id, last_updated, match_data FROM live_basketball ORDER BY last_updated DESC LIMIT 1")
        row = cur.fetchone()
        
        if row:
            mid, updated, data = row
            print(f"Match ID: {mid}")
            print(f"Last Updated: {updated} (Current System Time ~ 15:45)")
            
            # Test extraction
            raw_odds = get_odds(data)
            print(f"Extracted Odds: {raw_odds}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_basketball()
