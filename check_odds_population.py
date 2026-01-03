
import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_odds_data():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        tables = ['live_cricket', 'live_tennis', 'live_basketball', 'live_table_tennis', 'live_ice_hockey', 'live_esports']
        
        for table in tables:
            print(f"--- Checking {table} ---")
            cur.execute(f"SELECT count(*) FROM {table}")
            total = cur.fetchone()[0]
            
            cur.execute(f"SELECT count(*) FROM {table} WHERE other_odds IS NOT NULL")
            populated = cur.fetchone()[0]
            
            cur.execute(f"SELECT other_odds, match_data FROM {table} WHERE other_odds IS NOT NULL LIMIT 1")
            sample = cur.fetchone()
            
            print(f"Total Rows: {total}")
            print(f"Rows with other_odds: {populated}")
            if sample:
                print(f"Sample other_odds: {sample[0]}")
            else:
                print("Sample: None")
                
                # If None, let's check what's in match_data['odds'] or match_data['ext']
                # to see if we missed it.
                cur.execute(f"SELECT match_data FROM {table} LIMIT 1")
                raw_sample = cur.fetchone()
                if raw_sample:
                   import json
                   # try to pretty print a snippet
                   data = raw_sample[0]
                   # Extract potential odds locations for debugging
                   debug_info = {
                       'odds_key': data.get('odds'),
                       'ext_odds': data.get('ext', {}).get('odds') if isinstance(data.get('ext'), dict) else None
                   }
                   print(f"Raw Data Debug (Potential Odds): {debug_info}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_odds_data()
