
import psycopg2
import os

# DB Connection String
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def scan_table_columns(table_name):
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        print(f"\n--- Columns in {table_name} ---")
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}';
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"{row[0]} ({row[1]})")
            
        conn.close()
    except Exception as e:
        print(f"Error scanning {table_name}: {e}")

if __name__ == "__main__":
    scan_table_columns("live_football")
    scan_table_columns("live_cricket")
    scan_table_columns("live_tennis")
    scan_table_columns("live_basketball")
