
import psycopg2
import time

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def verify_status_fix():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Check specific IDs user complained about
        target_ids = ['VD9', 'YAX', 'YAY', 'YKD']
        
        print("Checking status for: ", target_ids)
        cur.execute(f"SELECT match_id, match_status, league FROM live_matches WHERE match_id IN {tuple(target_ids)};")
        rows = cur.fetchall()
        
        for row in rows:
            print(f"Match {row[0]}: Status='{row[1]}', League='{row[2]}'")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_status_fix()
