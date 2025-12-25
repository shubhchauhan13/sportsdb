import requests
import time
import random

# Common 1xBet mirrors and endpoints
DOMAINS = [
    "1xbet.com",
    "1xstavka.ru",
    "melbet.com",
    "betwinner.com",
    "22bet.com"
]

# Sport IDs: 2=Hockey, 10=Table Tennis, 40=Esports
SPORTS = {
    'ice-hockey': 2,
    'table-tennis': 10,
    'esports': 40
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://1xbet.com/live/ice-hockey/"
}

def check_endpoint(domain, sport_id):
    url = f"https://{domain}/LiveFeed/Get1x2_VZip"
    params = {
        "sports": sport_id,
        "count": 5,
        "mode": 4,
        "country": 1,
        "partner": 7,
        "getEmpty": "true"
    }
    
    print(f"Testing {domain} for sport {sport_id}...")
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get('Value', [])
            print(f"✅ SUCCESS: Found {len(matches)} matches")
            if matches:
                m = matches[0]
                print(f"   Sample: {m.get('O1')} vs {m.get('O2')}")
                # Odds structure in 1xBet
                # 'E' list often contains odds. E[i]['T'] is type, 'C' is value
            return True
        else:
            print(f"❌ FAILED: Status {resp.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:50]}")
    return False

print("--- Testing 1xBet Mirrors ---")
for sport_name, sport_id in SPORTS.items():
    print(f"\nScanning for {sport_name} (ID: {sport_id})")
    for domain in DOMAINS:
        if check_endpoint(domain, sport_id):
            break
