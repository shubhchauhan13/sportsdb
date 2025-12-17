import psycopg2
import os

DB_DSN = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def fix():
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    # 1. Drop dummy live_basketball if exists (check columns?)
    # or just DROP IF EXISTS to be safe and recreate empty
    tables = [
        'live_basketball', 'live_table_tennis', 
        'live_ice_hockey', 'live_esports', 'live_motorsport'
    ]
    
    for t in tables:
        print(f"Re-creating {t}...")
        try:
            cur.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
            print(f"Dropped {t}.")
        except: 
            conn.rollback()
            
        try:
            cur.execute(f"""
                CREATE TABLE {t} (
                    match_id TEXT PRIMARY KEY,
                    match_data JSONB,
                    home_team TEXT,
                    away_team TEXT,
                    status TEXT,
                    score TEXT,
                    batting_team TEXT,
                    is_live BOOLEAN DEFAULT FALSE,
                    home_score TEXT,
                    away_score TEXT,
                    home_odds TEXT,
                    away_odds TEXT,
                    draw_odds TEXT,
                    last_updated TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()
            print(f"Created {t} SUCCESS.")
        except Exception as e:
            print(f"Failed to create {t}: {e}")
            conn.rollback()
            
    conn.close()

if __name__ == "__main__":
    fix()
