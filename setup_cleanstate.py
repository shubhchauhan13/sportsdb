
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# DB Connection
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def setup_cleanstate_table():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print("Checking cleanstate table...")
        
        # Create table if not exists with all required columns
        # Note: 'status' is already used for event_state. We add 'match_status' for the broader status.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cleanstate (
                match_id TEXT PRIMARY KEY,
                title TEXT,
                league TEXT,
                team_a TEXT,
                team_b TEXT,
                batting_team TEXT,
                score TEXT,
                status TEXT, -- Stores event_state
                innings TEXT,
                odds JSONB,
                session JSONB,
                updated_at TIMESTAMP,
                match_status TEXT -- New column for Live/Upcoming/Completed
            );
        """)
        
        # Add columns if they don't exist (migrations)
        columns_to_add = [
            ("match_status", "TEXT"),
            ("league", "TEXT"),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                cur.execute(f"ALTER TABLE cleanstate ADD COLUMN {col_name} {col_type};")
                print(f"Added column: {col_name}")
            except psycopg2.errors.DuplicateColumn:
                print(f"Column already exists: {col_name}")
            except Exception as e:
                # If specific known error, ignore, else print
                if "already exists" not in str(e):
                    print(f"Error adding {col_name}: {e}")
        
        print("cleanstate table validation complete.")
        conn.close()
        
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    setup_cleanstate_table()
