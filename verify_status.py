import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def verify():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        sports = ['table-tennis', 'ice-hockey', 'esports']
        
        for sport in sports:
            table_name = f"live_{sport.replace('-', '_')}"
            print(f"\n--- {sport.upper()} ---")
            
            # Check Live
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE is_live = TRUE;")
            live_count = cur.fetchone()[0]
            
            # Check Total
            cur.execute(f"SELECT COUNT(*) FROM {table_name};")
            total_count = cur.fetchone()[0]
            
            print(f"Total: {total_count}")
            print(f"Live: {live_count}")
            
            if live_count == 0:
                print("⚠️ NO LIVE MATCHES.")
            else:
                print("✅ Live matches exist.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
