import psycopg2
import os

# DB Connection String from scraper_service.py
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check():
    try:
        print("Connecting to NeonDB...")

        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        


        print("\n[INFO] Live Tennis Sample (Verification):")
        cur.execute("SELECT match_id, status, score, home_team, away_team FROM live_tennis LIMIT 5;")
        rows = cur.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Status: {row[1]} | Score: {row[2]} | {row[3]} vs {row[4]}")
        
        conn.close()

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    check()
