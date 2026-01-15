import psycopg2
from datetime import datetime
import sys

# Connection String
DB_URL = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        tables = ['live_table_tennis', 'live_football', 'live_cricket']
        print("\n--- Final Freshness Check ---")
        for table in tables:
            try:
                cur.execute(f"SELECT MAX(last_updated), COUNT(*) FROM {table}")
                row = cur.fetchone()
                last_up = row[0]
                count = row[1]
                
                print(f"Table '{table}': {count} rows. Last Updated: {last_up}")
            except Exception as e:
                print(f"Table '{table}': {e}")

        conn.close()
    except Exception as e:
        print(f"[FATAL] {e}")

if __name__ == "__main__":
    check_db()
