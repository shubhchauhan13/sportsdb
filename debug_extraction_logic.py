
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_odds_current_logic(match):
    """
    Exact copy of the logic currently in scraper_service.py
    """
    odds = {'home': None, 'away': None, 'draw': None}
    
    # 0. Pre-extracted
    if 'odds' in match and isinstance(match['odds'], dict):
        return match['odds']
    
    try:
        ext = match.get('ext') or {}
        odds_data = ext.get('odds') or {}
        odd_items = odds_data.get('oddItems') or []
        
        # print(f"DEBUG: oddItems count: {len(odd_items)}") 
        
        # oddItems[1] typically contains the main odds
        if len(odd_items) > 1 and odd_items[1]:
            odd_arr = odd_items[1].get('odd', [])
            # print(f"DEBUG: odd_arr at index 1: {odd_arr}")
            
            if len(odd_arr) >= 3:
                # String '0' check
                val_h = odd_arr[0]
                val_a = odd_arr[2]
                
                odds['home'] = val_h if val_h and val_h != '0' else None
                odds['away'] = val_a if val_a and val_a != '0' else None
                
                if len(odd_arr) > 1:
                     val_d = odd_arr[1]
                     if val_d and val_d != '0':
                         odds['draw'] = val_d
    except Exception as e:
        print(f"Extraction Error: {e}")
        pass
        
    return odds

def debug_db_extraction():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Check Basketball (since we saw it had data before)
        print("--- Testing Basketball Extraction ---")
        cur.execute("SELECT match_id, match_data FROM live_basketball LIMIT 5")
        rows = cur.fetchall()
        
        for mid, data in rows:
            print(f"\nMatch: {mid}")
            
            # 1. Dig into the data manually to see what's there
            ext = data.get('ext') or {}
            odds_data = ext.get('odds') or {}
            odd_items = odds_data.get('oddItems') or []
            print(f"  oddItems present? {len(odd_items)}")
            if len(odd_items) > 0:
                print(f"  Item 0: {odd_items[0].get('odd')}")
            if len(odd_items) > 1:
                print(f"  Item 1: {odd_items[1].get('odd')}")


            # 2. Run logic
            extracted = get_odds_current_logic(data)
            print(f"  Extracted: {extracted}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_db_extraction()
