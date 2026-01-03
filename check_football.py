import psycopg2
import os
from datetime import datetime

# DB Connection String from scraper_service.py
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check():
    try:
        print("Connecting to NeonDB...")
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        print("\n[INFO] Live Football Sample (Latest 5):")
        cur.execute("SELECT match_id, home_team, away_team, score, status, last_updated FROM live_football ORDER BY last_updated DESC LIMIT 5;")
        rows = cur.fetchall()
        for row in rows:
            print(f"ID: {row[0]}")
            print(f"  Teams: {row[1]} vs {row[2]}")
            print(f"  Score: {row[3]}")
            print(f"  Status: {row[4]}")
            print(f"  Last Updated: {row[5]}")
            
        conn.close()

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    check()
