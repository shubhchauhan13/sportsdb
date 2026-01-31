import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def verify():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Check for unknown names
        cur.execute("SELECT COUNT(*) FROM live_football WHERE (home_team = 'Unknown' OR away_team = 'Unknown') AND match_id LIKE 's24_%';")
        unknown_count = cur.fetchone()[0]
        
        # Get sample names
        cur.execute("SELECT home_team, away_team FROM live_football WHERE match_id LIKE 's24_%' LIMIT 5;")
        samples = cur.fetchall()
        
        print(f"Unknown Names Count: {unknown_count}")
        print("Samples:")
        for s in samples:
            print(f"  {s[0]} vs {s[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
