import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    print("Connecting to DB...")
    conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=5)
    print("Connected!")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
