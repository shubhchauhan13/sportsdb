import psycopg2
import os

# DB Connection String from scraper_service.py
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check():
    try:
        print("Connecting to NeonDB...")
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Check Table Exists
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'live_matches');")
        exists = cur.fetchone()[0]
        if not exists:
            print("[ERROR] Table 'live_matches' does not exist!")
            return

        # Check Row Count
        cur.execute("SELECT count(*) FROM live_matches;")
        count = cur.fetchone()[0]
        print(f"[INFO] Total Rows in 'live_matches': {count}")
        
        if count > 0:
            # Show a sample
            cur.execute("SELECT match_id, last_updated, match_data->>'title' FROM live_matches LIMIT 5;")
            rows = cur.fetchall()
            print("\nSample Data:")
            for r in rows:
                print(f"- {r[0]} | {r[1]} | {r[2]}")
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    check()
