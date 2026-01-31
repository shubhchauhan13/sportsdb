
import psycopg2
import json

def debug_missing_odds():
    conn = psycopg2.connect('postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')
    cur = conn.cursor()
    
    print("Fetching Sofascore TT matches with missing odds...")
    cur.execute("""
        SELECT match_id, match_data 
        FROM live_table_tennis 
        WHERE match_id LIKE 'sf_%' 
        AND is_live = TRUE 
        AND (other_odds->>'home' IS NULL OR other_odds->>'home' = 'None')
        LIMIT 3
    """)
    
    rows = cur.fetchall()
    print(f"Found {len(rows)} samples.")
    
    for mid, data in rows:
        print(f"\n--- ID: {mid} ---")
        # In our Sofascore scraper, we stored the raw event in 'match_data_extra' inside the match_data
        # But wait, in upsert_matches we store `Json(m)` as match_data.
        # So `data` IS the object we constructed.
        # Let's check `match_data_extra` if available.
        
        extra = data.get('match_data_extra')
        if extra:
            print("Raw Event Keys:", extra.keys())
            print("Slug:", extra.get('slug'))
            print("Status:", extra.get('status'))
            # We don't store the odds response in match_data, only the result.
            # But we can see if it has 'vote' or other indicators of being valid.
        else:
            print("No 'match_data_extra' found.")
            print("Keys:", data.keys())

if __name__ == "__main__":
    debug_missing_odds()
