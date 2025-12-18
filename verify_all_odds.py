import psycopg2
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def verify():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        sports = ['football', 'cricket', 'tennis', 'basketball', 'table-tennis', 'ice-hockey', 'esports']
        
        print(f"{'Sport':<15} | {'Total':<8} | {'With Odds':<10} | {'% Coverage':<10}")
        print("-" * 50)
        
        for sport in sports:
            table_name = f"live_{sport.replace('-', '_')}"
            
            # Count total
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                total = cur.fetchone()[0]
                
                # Count with odds
                cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE (CAST(home_odds AS FLOAT) > 0 OR CAST(away_odds AS FLOAT) > 0);")
                with_odds = cur.fetchone()[0]
                
                pct = (with_odds / total * 100) if total > 0 else 0
                
                print(f"{sport:<15} | {total:<8} | {with_odds:<10} | {pct:.1f}%")
            except Exception as table_err:
                print(f"{sport:<15} | ERROR: {table_err}")
                conn.rollback()
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
