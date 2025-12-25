
import json

def get_odds_robust(match):
    odds = {'home': None, 'away': None, 'draw': None}
    
    # 0. Pre-extracted
    if 'odds' in match and isinstance(match['odds'], dict):
        return match['odds']
    
    try:
        ext = match.get('ext') or {}
        odds_data = ext.get('odds') or {}
        odd_items = odds_data.get('oddItems') or []
        
        # Iterate to find the main odds (usually items[1], but let's be flexible)
        # Strategy: Look for the first item with length >= 3 and non-zero values
        best_odds = None
        
        # Priority: Index 1 (Match winner usually), then 0 or others
        indices_to_check = [1, 0, 2]
        
        for idx in indices_to_check:
            if idx < len(odd_items):
                item = odd_items[idx]
                odd_arr = item.get('odd', [])
                if len(odd_arr) >= 2:
                    # Check validity
                    # Usually [Home, Draw, Away] or [Home, Away]
                    # Filter out zero/empty
                    valid_vals = [v for v in odd_arr if v and str(v) != '0']
                    if len(valid_vals) >= 2:
                        best_odds = odd_arr
                        print(f"DEBUG: Found valid odds at index {idx}: {best_odds}")
                        break
        
        if best_odds and len(best_odds) >= 2:
            # Helper to clean value
            def clean(v):
                return v if v and str(v) != '0' else None

            # Mapping depends on length?
            # If 3+ values: H, D, A ?
            # Basketball sample has 4 values: ['0.83', '2.5', '0.83', '0'] -> Home=0.83, Away=0.83? No, that looks like H/A handicap?
            # Wait, item[1] in basketball sample is ['1.67', '0', '2.1', '0'] -> H=1.67, A=2.1 (Draw=0)
            
            # Logic:
            # 0 -> Home
            # 1 -> Draw (if exists/valid)
            # 2 -> Away (if exists/valid) OR 1 is Away if length is 2?
            # AiScore usually structure is H, D, A, ...
            
            odds['home'] = clean(best_odds[0])
            
            if len(best_odds) >= 3:
                odds['draw'] = clean(best_odds[1])
                odds['away'] = clean(best_odds[2])
            elif len(best_odds) == 2:
                # Assuming H, A
                odds['away'] = clean(best_odds[1])

            # Special case for Basketball/Tennis often D is 0, so index 2 is Away
            if not odds['away'] and len(best_odds) > 2:
                 odds['away'] = clean(best_odds[2])

    except Exception as e:
        print(f"Error: {e}")
        pass
        
    return odds

if __name__ == "__main__":
    with open("sample_basketball.json", "r") as f:
        data = json.load(f)
        print("Testing Basketball Sample:")
        print(get_odds_robust(data))
        
    try:
        with open("sample_cricket_live.json", "r") as f:
            c_data = json.load(f)
            print("\nTesting Cricket Sample:")
            print(get_odds_robust(c_data))
    except: pass

    try:
        with open("sample_tennis.json", "r") as f:
            t_data = json.load(f)
            print("\nTesting Tennis Sample:")
            print(get_odds_robust(t_data))
    except: pass
