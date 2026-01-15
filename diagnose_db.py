import psycopg2
import os
from datetime import datetime
import sys

# Connection String provided by user
DB_URL = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_db():
    print(f"[{datetime.now()}] Connecting to DB...")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        print("[SUCCESS] Connected.")
        
        # List of tables to check
        tables = ['live_football', 'live_cricket', 'live_basketball', 'live_tennis']
        
        print("\n--- Freshness Check ---")
        for table in tables:
            try:
                cur.execute(f"SELECT MAX(last_updated), COUNT(*) FROM {table}")
                row = cur.fetchone()
                last_up = row[0]
                count = row[1]
                
                if last_up:
                    delta = datetime.now() - last_up
                    print(f"Table '{table}': {count} rows. Last Updated: {last_up} ({delta} ago)")
                else:
                    print(f"Table '{table}': {count} rows. Last Updated: NEVER")
                    
            except Exception as e:
                print(f"Table '{table}': Error - {e}")
                conn.rollback()

        print("\n--- Write Test ---")
        try:
            # Create a test table if not exists
            cur.execute("CREATE TABLE IF NOT EXISTS connection_test (id SERIAL PRIMARY KEY, ts TIMESTAMP);")
            cur.execute("INSERT INTO connection_test (ts) VALUES (NOW());")
            conn.commit()
            print("[SUCCESS] Write test passed (committed).")
        except Exception as e:
            print(f"[FAIL] Write test failed: {e}")
            conn.rollback()
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"[FATAL] Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_db()
