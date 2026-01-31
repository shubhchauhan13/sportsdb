
import psycopg2
import time

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

NEW_SPORTS = [
    'live_volleyball',
    'live_baseball',
    'live_badminton',
    'live_american_football',
    'live_handball',
    'live_water_polo',
    'live_snooker',
    'live_rugby',
    'live_cricket',
    'live_tennis'
]

def check_counts():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        print(f"{'Table':<25} | {'Rows':<6} | {'Live':<6} | {'With Odds (Std)'}")
        print("-" * 65)
        
        for table in NEW_SPORTS:
            cur.execute(f"SELECT count(*) FROM {table}")
            total = cur.fetchone()[0]
            
            cur.execute(f"SELECT count(*) FROM {table} WHERE is_live=TRUE")
            live = cur.fetchone()[0]
            
            # Check standard odds columns
            cur.execute(f"SELECT count(*) FROM {table} WHERE home_odds IS NOT NULL AND home_odds != 'None'")
            with_odds = cur.fetchone()[0]
            
            print(f"{table:<25} | {total:<6} | {live:<6} | {with_odds}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_counts()
