import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_db():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    cur = conn.cursor()
    
    tables = [
        'live_cricket', 'live_football', 'live_tennis', 
        'live_basketball', 'live_table_tennis', 
        'live_ice_hockey', 'live_esports', 'live_motorsport'
    ]
    
    print("--- Table Verification ---")
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"[OK] {t}: {count} rows")
            
            # Check for odds
            if count > 0:
                cur.execute(f"SELECT home_odds, away_odds, draw_odds FROM {t} LIMIT 1")
                odds = cur.fetchone()
                print(f"    Odds Sample: Home={odds[0]}, Away={odds[1]}, Draw={odds[2]}")
        except Exception as e:
            print(f"[FAIL] {t}: {e}")
            conn.rollback()

    conn.close()

if __name__ == "__main__":
    check_db()
