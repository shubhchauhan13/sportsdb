
import psycopg2
import json
from collections import Counter

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def analyze_odds():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()

        # 1. Analyze Cricket Odds (Live Only)
        print("\n--- CRICKET ODDS ANALYSIS (Live Only) ---")
        cur.execute("""
            SELECT match_id, status, is_live, other_odds, match_data 
            FROM live_cricket 
            WHERE is_live = TRUE
        """)
        rows = cur.fetchall()
        print(f"Total Live Cricket Matches: {len(rows)}")
        
        valid_odds_count = 0
        for row in rows:
            mid, status, is_live, odds, data = row
            has_odds = False
            if odds and isinstance(odds, dict):
                # Check if any value in the dict is non-null/non-zero
                if any(v for v in odds.values() if v and v != '0' and v != 0):
                    has_odds = True
            
            if has_odds:
                valid_odds_count += 1
                print(f"  [WITH ODDS] ID: {mid}, Status: {status}, Odds: {odds}")
            else:
                # Debug why missing
                # Check raw data for 'odds' key or 'ext.odds'
                raw_odds_key = data.get('odds')
                raw_ext_odds = data.get('ext', {}).get('odds') if isinstance(data.get('ext'), dict) else None
                print(f"  [NO ODDS]   ID: {mid}, Status: {status}") 
                # print(f"    Raw 'odds' key: {raw_odds_key}")
                # print(f"    Raw 'ext.odds': {str(raw_ext_odds)[:100]}")

        print(f"Live Cricket Matches with Odds: {valid_odds_count}/{len(rows)}")


        # 2. Analyze Potential Placeholders (Other Sports)
        print("\n--- PLACEHOLDER ANALYSIS (Other Sports) ---")
        sports = ['live_tennis', 'live_basketball', 'live_table_tennis', 'live_ice_hockey']
        
        for table in sports:
            print(f"\nScanning {table}...")
            cur.execute(f"SELECT other_odds FROM {table} WHERE other_odds IS NOT NULL")
            all_odds = cur.fetchall()
            
            # Count frequency of full odds objects to see if they are identical
            # Convert dict to string for counting
            odds_strings = []
            for (o,) in all_odds:
                # Filter out empty/null odds
                if not o: continue
                # Normalized string
                s = json.dumps(o, sort_keys=True)
                odds_strings.append(s)
            
            if not odds_strings:
                print("  No odds data found.")
                continue
                
            c = Counter(odds_strings)
            print(f"  Total Odds Entries: {len(odds_strings)}")
            print(f"  Unique Odds Variations: {len(c)}")
            print("  Top 5 Most Frequent Odds:")
            for val, count in c.most_common(5):
                print(f"    Count {count}: {val}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_odds()
