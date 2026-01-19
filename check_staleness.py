
import psycopg2
import os
from datetime import datetime
import time

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

SPORTS_TABLES = {
    'cricket': 'live_cricket',
    'football': 'live_football',
    'tennis': 'live_tennis',
    'basketball': 'live_basketball',
    'table-tennis': 'live_table_tennis',
    'ice-hockey': 'live_ice_hockey',
    'esports': 'live_esports',
    'volleyball': 'live_volleyball',
    'baseball': 'live_baseball',
    'badminton': 'live_badminton',
    'american-football': 'live_american_football',
    'handball': 'live_handball',
    'water-polo': 'live_water_polo',
    'snooker': 'live_snooker',
    'rugby': 'live_rugby',
    'motorsport': 'live_motorsport'
}

def check_staleness():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        print(f"{'SPORT':<20} | {'LAST UPDATED (UTC Approx)':<30} | {'STATUS'}")
        print("-" * 70)
        
        now = datetime.utcnow()
        
        for sport, table in SPORTS_TABLES.items():
            try:
                cur.execute(f"SELECT MAX(last_updated) FROM {table}")
                res = cur.fetchone()
                last_update = res[0] if res else None
                
                if last_update:
                    # Naive to UTC
                    # Assuming DB stores naive timestamps as UTC or has tzinfo
                    if last_update.tzinfo:
                         # convert to utc
                         last_update = last_update.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    
                    diff = (now - last_update).total_seconds()
                    minutes = int(diff / 60)
                    
                    status = "OK"
                    if minutes > 15:
                        status = f"STALE ({minutes}m)"
                    
                    print(f"{sport:<20} | {str(last_update):<30} | {status}")
                else:
                    print(f"{sport:<20} | {'None':<30} | EMPTY")
            except Exception as e:
                print(f"{sport:<20} | {'ERROR':<30} | Table missing?")
                
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    check_staleness()
