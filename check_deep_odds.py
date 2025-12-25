
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_deep():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    cur = conn.cursor()
    
    tables = ['live_basketall', 'live_tennis', 'live_cricket', 'live_basketball'] # Typo in list but safe
    

    for t in ['live_basketball', 'live_tennis', 'live_cricket', 'live_table_tennis', 'live_ice_hockey']:
        print(f"Checking {t} for VALID odds values...")
        try:
            # Check for any row where home is not null
            cur.execute(f"SELECT count(*) FROM {t} WHERE other_odds->>'home' IS NOT NULL")
            count = cur.fetchone()[0]
            print(f"  {t}: {count} rows with valid 'home' odds")
            
            if count > 0:
                cur.execute(f"SELECT other_odds FROM {t} WHERE other_odds->>'home' IS NOT NULL LIMIT 1")
                print(f"  Sample: {cur.fetchone()[0]}")
            else:
                # Check how many live matches exist total
                cur.execute(f"SELECT count(*) FROM {t} WHERE is_live=TRUE")
                live_count = cur.fetchone()[0]
                print(f"  {t}: {live_count} LIVE matches found (but 0 valid odds)")
        except Exception as e:
            print(f"  Error querying {t}: {e}")
            
    conn.close()

if __name__ == "__main__":
    check_deep()
