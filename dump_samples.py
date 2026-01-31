
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def dump_samples():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # 1. Cricket
        print("Fetching Cricket Sample...")
        cur.execute("SELECT match_id, match_data FROM live_cricket WHERE is_live = TRUE LIMIT 1")
        row = cur.fetchone()
        if row:
            with open("sample_cricket_live.json", "w") as f:
                json.dump(row[1], f, indent=2)
            print(f"Dumped sample_cricket_live.json (ID: {row[0]})")

        # 2. Basketball
        print("Fetching Basketball Sample...")
        cur.execute("SELECT match_id, match_data FROM live_basketball LIMIT 1")
        row = cur.fetchone()
        if row:
            with open("sample_basketball.json", "w") as f:
                json.dump(row[1], f, indent=2)
            print(f"Dumped sample_basketball.json (ID: {row[0]})")
            
        # 3. Tennis
        print("Fetching Tennis Sample...")
        cur.execute("SELECT match_id, match_data FROM live_tennis WHERE is_live=TRUE LIMIT 1")
        row = cur.fetchone()
        if not row:
             cur.execute("SELECT match_id, match_data FROM live_tennis LIMIT 1")
             row = cur.fetchone()
             
        if row:
            with open("sample_tennis.json", "w") as f:
                json.dump(row[1], f, indent=2)
            print(f"Dumped sample_tennis.json (ID: {row[0]})")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_samples()
