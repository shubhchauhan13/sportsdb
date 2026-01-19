import requests
import json
import time

def check_sofascore_cricket():
    # Headers to mimic a browser/legitimate client
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }

    url = "https://www.sofascore.com/api/v1/sport/cricket/events/live"
    
    print(f"Fetching: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            events = data.get('events', [])
            print(f"Found {len(events)} live cricket events.")
            
            if events:
                print("\nSample Event Data:")
                print(json.dumps(events[0], indent=2))
        else:
            print("Failed to fetch data.")
            print(resp.text[:500])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_sofascore_cricket()
