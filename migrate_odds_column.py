
import psycopg2
import os

# DB Connection String
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

TABLES_TO_MIGRATE = [
    'live_cricket',
    'live_tennis',
    'live_basketball',
    'live_table_tennis',
    'live_ice_hockey',
    'live_esports'
]

def migrate():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        for table in TABLES_TO_MIGRATE:
            print(f"Migrating {table}...")
            try:
                # Add column if not exists
                cur.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS other_odds JSONB;
                """)
                print(f"  [SUCCESS] Added other_odds to {table}")
            except Exception as e:
                print(f"  [ERROR] Failed to alter {table}: {e}")
                conn.rollback() # Rollback to proceed to next
                continue
            
            conn.commit()
            
        print("\nMigration Completed.")
        conn.close()
        
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    migrate()
