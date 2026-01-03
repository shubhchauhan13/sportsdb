
import psycopg2
import json

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_unknown_status():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Get matches with Unknown status
        cur.execute("SELECT match_id, match_data FROM live_matches WHERE match_status = 'Unknown' LIMIT 3;")
        rows = cur.fetchall()
        
        print(f"Found {len(rows)} matches with Unknown status.")
        
        for row in rows:
            mid = row[0]
            raw = row[1].get('raw', {})
            print(f"\n--- Match {mid} ---")
            print(f"Status Code (a): '{raw.get('a')}'")
            print(f"Result (res): '{raw.get('res')}'")
            print(f"StartTime (ti): {raw.get('ti')}")
            print(f"Score A (j): '{raw.get('j')}'")
            print(f"Score B (k): '{raw.get('k')}'")
            print(f"Format (fo): '{raw.get('fo')}'")
            print(f"Full Raw: {json.dumps(raw)}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_unknown_status()
