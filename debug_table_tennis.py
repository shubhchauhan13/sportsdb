
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def debug_tt():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()

        # Fetch 5 samples where odds are missing
        cur.execute("""
            SELECT match_id, match_data 
            FROM live_table_tennis 
            WHERE other_odds IS NULL 
            LIMIT 5
        """)
        rows = cur.fetchall()
        
        print(f"Inspecting {len(rows)} Table Tennis matches with missing odds...\n")
        
        for mid, data in rows:
            print(f"--- MATCH ID: {mid} ---")
            # Print keys to understand high level structure
            print(f"Top-level keys: {list(data.keys())}")
            
            # Check generically for 'odds' string in keys recursively or values? 
            # For now, let's dump the first level relevant keys
            # Often data is in 'events', 'odds', 'markets', 'structure'
            
            if 'odds' in data:
                print(f"Found 'odds' key: {data['odds']}")
                
            if 'markets' in data:
                print(f"Found 'markets' key: {str(data['markets'])[:200]}...") # truncate
                
            # If using specialized scraper, maybe it's in 'ext' or 'detailed'
            if 'ext' in data:
                print(f"Found 'ext' key: {data['ext']}")
                
            # Print a small dump of the JSON to visually inspect
            print("Snippet of data:")
            print(json.dumps(data, indent=2)[:1000]) # First 1000 chars
            print("\n")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_tt()
