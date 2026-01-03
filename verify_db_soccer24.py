import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def verify():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Check count of s24 matches in live_football
        cur.execute("SELECT COUNT(*), COUNT(CASE WHEN is_live THEN 1 END) FROM live_football WHERE match_id LIKE 's24_%';")
        total, live = cur.fetchone()
        
        print(f"Soccer24 Matches in DB: Total={total}, Live={live}")
        
        if total > 0:
            print("✅ SUCCESS: Soccer24 data is being stored.")
        else:
            print("❌ FAILURE: No Soccer24 data found.")
            
        # Also check last_updated of s24 matches
        cur.execute("SELECT MAX(last_updated) FROM live_football WHERE match_id LIKE 's24_%';")
        last_upd = cur.fetchone()[0]
        print(f"Last Updated: {last_upd}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
