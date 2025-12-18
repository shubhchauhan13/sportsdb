import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def clear():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute("DELETE FROM live_football WHERE match_id LIKE 's24_%';")
        conn.commit()
        print(f"Deleted {cur.rowcount} stale rows.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clear()
