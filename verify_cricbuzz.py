import requests
from bs4 import BeautifulSoup
import re

# Cricbuzz Live Scores Page
URL = "https://www.cricbuzz.com/cricket-match/live-scores"

def get_cricbuzz_scores():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"[*] Fetching Cricbuzz: {URL}")
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        print(f"[*] Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all match links
            # Pattern: <a href="/live-cricket-scores/..." title="...">
            match_links = soup.find_all('a', href=re.compile(r"^/live-cricket-scores/"))
            
            print(f"[*] Found {len(match_links)} potential match links")
            
            seen_matches = set()
            
            for link in match_links:
                title = link.get('title', '')
                href = link.get('href', '')
                
                # Deduplicate based on href
                if href in seen_matches:
                    continue
                seen_matches.add(href)
                
                # Filter out garbage links if any
                if not title:
                    continue
                    
                # Parse Title for Status
                # "Team A vs Team B, Nth Match - Status"
                print(f"\n[MATCH] {title}")
                print(f"   Link: {href}")
                
                # Extract simple text from children divs
                # Usually text-white has teams, text-xs has info
                team_div = link.find('div', class_='text-white')
                info_div = link.find('div', class_='text-[#d1d1d1]') # Updated to match observed class
                
                if team_div:
                    print(f"   Teams (Div): {team_div.get_text(strip=True)}")
                if info_div:
                    print(f"   Info (Div): {info_div.get_text(strip=True)}")

        else:
            print(f"[FAIL] Error: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] Crash: {e}")

if __name__ == "__main__":
    get_cricbuzz_scores()
