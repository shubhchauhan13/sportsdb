import psycopg2
import sys

# use the exact string from the file
DB_DSN = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def diag():
    print("Connecting...")
    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()
        
        # 1. List ALL tables
        print("\n--- Listing Tables (pg_catalog) ---")
        cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
        tables = cur.fetchall()
        for t in tables:
            print(f"Table: {t[0]}")
            
        # 2. Check live_basketball specifically
        print("\n--- Checking live_basketball ---")
        try:
            cur.execute("SELECT count(*) FROM live_basketball")
            print(f"live_basketball exists! Count: {cur.fetchone()[0]}")
        except Exception as e:
            print(f"live_basketball access FAILED: {e}")
            conn.rollback()
            
            # 3. Try Creating it
            print("Attempting Creation...")
            cur.execute("CREATE TABLE live_basketball (id serial primary key);")
            conn.commit()
            print("Creation Committed.")
            
    except Exception as e:
        print(f"FATAL: {e}")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    diag()
