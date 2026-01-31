"""
Database Schema Setup for Sportsbook

Creates all required tables in the new NeonDB instance.
"""

import psycopg2

NEW_DB_URL = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

SPORTS_TABLES = [
    "live_football",
    "live_cricket", 
    "live_basketball",
    "live_tennis",
    "live_table_tennis",
    "live_ice_hockey",
    "live_esports",
    "live_volleyball",
    "live_baseball",
    "live_badminton",
    "live_american_football",
    "live_handball",
    "live_water_polo",
    "live_snooker",
    "live_rugby",
    "live_motorsport"
]

def create_schema():
    """Create all sportsbook tables."""
    print("Connecting to new NeonDB...")
    
    try:
        conn = psycopg2.connect(NEW_DB_URL, connect_timeout=30)
        cur = conn.cursor()
        print("Connected successfully!")
        
        for table in SPORTS_TABLES:
            print(f"Creating table: {table}...")
            
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    match_id VARCHAR(255) PRIMARY KEY,
                    match_data JSONB,
                    home_team VARCHAR(255),
                    away_team VARCHAR(255),
                    status VARCHAR(50),
                    score VARCHAR(100),
                    batting_team VARCHAR(255),
                    is_live BOOLEAN DEFAULT FALSE,
                    home_score VARCHAR(50),
                    away_score VARCHAR(50),
                    home_odds DECIMAL(10,2),
                    away_odds DECIMAL(10,2),
                    draw_odds DECIMAL(10,2),
                    other_odds JSONB,
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create index on is_live for faster queries
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table}_is_live 
                ON {table} (is_live);
            """)
            
            # Create index on last_updated for staleness checks
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table}_last_updated 
                ON {table} (last_updated);
            """)
        
        # Create connection test table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        conn.commit()
        print(f"\n✅ Created {len(SPORTS_TABLES)} sport tables successfully!")
        
        # Verify by listing tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        print(f"\nTables in database ({len(tables)}):")
        for t in tables:
            print(f"  - {t[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    create_schema()
