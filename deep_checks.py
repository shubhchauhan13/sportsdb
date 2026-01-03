
import psycopg2
import json
from collections import Counter
import os

DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_B3YTEO0DxrMV@ep-old-voice-ahlg0kao-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def is_empty_odds(odds):
    if odds is None:
        return True
    if isinstance(odds, dict):
        if not odds:
            return True
        # Check if all values are None, 0, "0", or "-"
        valid_values = [v for v in odds.values() if v and v != '0' and v != 0 and v != '-']
        return len(valid_values) == 0
    return False

def analyze_database():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()

        # Get all live_ tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'live_%'
        """)
        tables = [row[0] for row in cur.fetchall()]
        tables.sort()

        print(f"Found {len(tables)} sports tables: {', '.join(tables)}")
        
        sports_no_odds = []
        total_matches_with_null_odds = 0
        
        report = []

        print("\n" + "="*60)
        print(f"{'SPORT TABLE':<25} | {'TOTAL':<8} | {'NULL/EMPTY':<12} | {'% MISSING':<10}")
        print("-" * 60)


        print("\n" + "="*80)
        print(f"{'SPORT TABLE':<25} | {'TOTAL':<6} | {'LIVE':<6} | {'NULL (LIVE)':<12} | {'% MISSING (LIVE)':<16}")
        print("-" * 80)

        for table in tables:
            # Get columns
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            columns = [row[0] for row in cur.fetchall()]
            
            has_other_odds = 'other_odds' in columns
            has_home_odds = 'home_odds' in columns
            has_is_live = 'is_live' in columns
            
            if not has_other_odds and not has_home_odds:
                continue

            select_cols = []
            if has_other_odds: select_cols.append("other_odds")
            if has_home_odds: select_cols.append("home_odds")
            
            query_cols = ", ".join(select_cols)
            if has_is_live:
                query = f"SELECT {query_cols}, is_live FROM {table}"
            else:
                query = f"SELECT {query_cols}, FALSE FROM {table}" # Assume false if no col
                
            cur.execute(query)
            rows = cur.fetchall()
            
            total_count = len(rows)
            live_count = 0
            live_null_count = 0
            
            total_null_count = 0
            
            for row in rows:
                # Last element is is_live
                is_live = row[-1]
                odds_vals = row[:-1]
                
                row_has_odds = False
                
                # Check other_odds (first col if present)
                current_idx = 0
                if has_other_odds:
                    if not is_empty_odds(odds_vals[current_idx]):
                        row_has_odds = True
                    current_idx += 1
                
                if not row_has_odds and has_home_odds:
                    val = odds_vals[current_idx]
                    if val and val != '0' and val != '-' and val != 'null':
                        row_has_odds = True
                
                if not row_has_odds:
                    total_null_count += 1
                    if is_live:
                        live_null_count += 1
                
                if is_live:
                    live_count += 1
            
            pct_live_missing = (live_null_count / live_count * 100) if live_count > 0 else 0.0
            
            print(f"{table:<25} | {total_count:<6} | {live_count:<6} | {live_null_count:<12} | {pct_live_missing:.1f}%")
            
            if live_count > 0 and live_null_count == live_count:
                sports_no_odds.append(table)
            
            total_matches_with_null_odds += total_null_count

        print("="*60)
        
        print("\n--- SUMMARY REPORT ---")
        print(f"1. Sports with NO odds at all in ALL matches ({len(sports_no_odds)}):")
        for s in sports_no_odds:
            print(f"   - {s}")
            
        print(f"\n2. Total matches with NULL/Empty odds across all sports: {total_matches_with_null_odds}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_database()
