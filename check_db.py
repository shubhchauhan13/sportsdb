import psycopg2
import os

# DB Connection String from scraper_service.py
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check():
    try:
        print("Connecting to NeonDB...")

        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        



        print("\n[INFO] Live Cricket Sample (Data Freshness):")
        cur.execute("SELECT match_id, score, last_updated AT TIME ZONE 'UTC' FROM live_cricket LIMIT 5;")
        rows = cur.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Score: {row[1]} | Updated: {row[2]}")
        
        conn.close()

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    check()
