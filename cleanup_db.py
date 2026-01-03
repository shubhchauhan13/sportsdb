import psycopg2

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

def cleanup():
    print("Connecting to NeonDB...")
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    cur = conn.cursor()
    
    # 1. Show current state
    print("\n[BEFORE] All records in live_cricket:")
    cur.execute("SELECT match_id, home_team, score, last_updated FROM live_cricket ORDER BY last_updated DESC;")
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")
    
    print(f"\nTotal records: {len(rows)}")
    
    # 2. Delete old numeric ID records (from Sofascore)
    # AiScore IDs are alphanumeric like 'l6ke6hrm6vvhvq5'
    # Sofascore IDs are purely numeric like '108801'
    print("\n[CLEANUP] Deleting old Sofascore records (numeric IDs)...")
    cur.execute("DELETE FROM live_cricket WHERE match_id ~ '^[0-9]+$';")
    deleted = cur.rowcount
    print(f"  Deleted {deleted} old records.")
    
    conn.commit()
    
    # 3. Show remaining
    print("\n[AFTER] Remaining records:")
    cur.execute("SELECT match_id, home_team, score, last_updated FROM live_cricket ORDER BY last_updated DESC;")
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")
        
    print(f"\nTotal remaining: {len(rows)}")
    
    conn.close()
    print("\n[DONE] Cleanup complete!")

if __name__ == "__main__":
    cleanup()
