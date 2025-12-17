import psycopg2
import os

DB_DSN = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_odds():
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    # Check cricket for odds
    cur.execute("SELECT match_id, home_odds, away_odds FROM live_cricket WHERE is_live=TRUE LIMIT 5")
    rows = cur.fetchall()
    print("--- Cricket Odds ---")
    for r in rows:
        print(r)
        
    conn.close()

if __name__ == "__main__":
    check_odds()
