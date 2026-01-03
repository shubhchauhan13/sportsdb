import psycopg2
import os

# DB Connection String from scraper_service.py
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check():
    try:
        print("Connecting to NeonDB...")

        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        



        print("\n[INFO] Live Cricket Sample (Detailed):")
        cur.execute("SELECT match_id, home_team, away_team, score, status, match_data, last_updated FROM live_cricket ORDER BY last_updated DESC LIMIT 5;")
        rows = cur.fetchall()
        for row in rows:
            print(f"ID: {row[0]}")
            print(f"  Teams: {row[1]} vs {row[2]}")
            print(f"  Score: {row[3]}")
            print(f"  Status: {row[4]}")
            print(f"  Last Updated: {row[6]}")
            # match_data is a dictionary (JSONB)
            # print(f"  Raw Data Sample: {str(row[5])[:100]}...")

        
        conn.close()

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    check()
