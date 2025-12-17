import json

def inspect():
    with open('aiscore_data_live.json', 'r') as f:
        data = json.load(f)
        
    # NUXT structure usually: data.state...
    state = data.get('state', {})
    
    # 1. Team map
    teams = {}
    # Look for 'teams' in various places
    # Based on Step 132, it's in data.state.MatchesFuture.teams ?? Or matches?
    # Let's search recursively or just look at known keys
    
    # In Step 132: state.MatchesFuture.teams
    if 'MatchesFuture' in state:
        for t in state['MatchesFuture'].get('teams', []):
            teams[t['id']] = t['name']
            
    # Also check other potential locations
    
    print(f"Found {len(teams)} teams.")
    
    # Recursive search for objects with 'matchStatus'
    def search(obj, path):
        if isinstance(obj, dict):
            if 'matchStatus' in obj:
                # print(f"[FOUND] Match at {path}")
                # print(json.dumps(obj, indent=2))
                if 'ckScores' in obj:
                    print(f"--- ckScores for {obj.get('id')} ---")
                    print(json.dumps(obj['ckScores'], indent=2))
                return
            for k, v in obj.items():
                search(v, path + "." + k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                search(item, path + f"[{i}]")
                
    search(data, "root")


if __name__ == "__main__":
    inspect()
