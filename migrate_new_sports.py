
import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Include other_odds in schema
TABLE_SCHEMA = """
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
    other_odds JSONB,
    last_updated TIMESTAMP
"""

NEW_SPORTS = [
    'live_volleyball',
    'live_baseball',
    'live_badminton',
    'live_american_football',
    'live_handball',
    'live_water_polo',
    'live_snooker',
    'live_rugby'
]

def migrate():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        for table in NEW_SPORTS:
            print(f"Creating table {table}...")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({TABLE_SCHEMA});")
            
        conn.commit()
        conn.close()
        print("Migration successful.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
