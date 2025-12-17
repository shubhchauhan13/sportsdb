import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Sport Configuration (Copy from service to ensure parity)
SPORTS_CONFIG = {
    'cricket':       {'table': 'live_cricket'},
    'football':      {'table': 'live_football'},
    'tennis':        {'table': 'live_tennis'},
    'basketball':    {'table': 'live_basketball'},
    'table-tennis':  {'table': 'live_table_tennis'},
    'ice-hockey':    {'table': 'live_ice_hockey'},
    'esports':       {'table': 'live_esports'},
    'motorsport':    {'table': 'live_motorsport'} 
}

def setup():
    try:
        print("Connecting to DB...")
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        for sport, config in SPORTS_CONFIG.items():
            table = config['table']
            print(f"Setting up {table}...")
            
            # 1. Create Table
            try:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
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
                print(f"  - CREATE logic executed.")
            except Exception as e:
                print(f"  - CREATE FAILED: {e}")
                conn.rollback()
                continue
            
            # 2. Add Columns (Idempotent)
            columns = [
                ('batting_team', 'TEXT'),
                ('is_live', 'BOOLEAN DEFAULT FALSE'),
                ('home_score', 'TEXT'),
                ('away_score', 'TEXT'),
                ('home_odds', 'TEXT'),
                ('away_odds', 'TEXT'),
                ('draw_odds', 'TEXT')
            ]
            for col_name, col_type in columns:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};")
                    # print(f"  - Added {col_name}")
                except Exception as e:
                    # Ignore "exists" error
                    conn.rollback()
            
            conn.commit()
            print(f"  - Committed {table}.")
            
        conn.close()
        print("Setup Complete.")
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    setup()
