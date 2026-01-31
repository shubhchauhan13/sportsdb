import psycopg2
import json

# DB Connection String
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def analyze_coverage():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        cur.execute("SELECT match_data FROM live_matches;")
        rows = cur.fetchall()
        
        total = len(rows)
        status_counts = {"Live": 0, "Upcoming": 0, "Completed": 0, "Unknown": 0}
        
        for r in rows:
            data = r[0] # JSONB
            status = data.get("match_status", "Unknown")
            is_live = data.get("is_live", False)
            title = data.get("title", "Unknown")
            
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts["Unknown"] += 1
                
        print(f"Total Matches in DB: {total}")
        print("Breakdown by Status:")
        for k, v in status_counts.items():
            print(f"  - {k}: {v}")
            
        print("\nSchema Sample (First Row):")
        if rows:
            print(json.dumps(rows[0][0], indent=2))
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_coverage()
