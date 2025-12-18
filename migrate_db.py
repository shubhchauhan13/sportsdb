import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def migrate():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        tables = [
            'live_cricket', 'live_football', 'live_tennis', 
            'live_basketball', 'live_table_tennis', 
            'live_ice_hockey', 'live_esports'
        ]
        
        for table in tables:
            print(f"Migrating {table}...")
            # Add column
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS sport_key VARCHAR(50);")
            # Add index
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_sport_key_{table} ON {table}(sport_key);")
        
        conn.commit()
        print("✅ Migration Successful: Added sport_key column to all tables.")
        conn.close()
    except Exception as e:
        print(f"❌ Migration Failed: {e}")

if __name__ == "__main__":
    migrate()
