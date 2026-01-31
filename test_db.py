import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    print("Connecting to DB...")
    conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=5)
    print("Connected!")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
