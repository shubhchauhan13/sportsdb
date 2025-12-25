
from scraper_service import get_odds
import json

match_with_odds = {
  "id": "oj7xpsvw856t4kg",
  "ext": {
    "odds": {
      "oddItems": [
        {
          "odd": [
            "1.44",
            "-1.5",
            "2.62",
            "0"
          ]
        },
        {
          "odd": [
            "2.1",
            "0",
            "1.66",
            "0"
          ]
        },
        {
          "odd": [
            "1.9",
            "78.5",
            "1.8",
            "0"
          ]
        }
      ]
    },
    "hasPlayerTotal": 1
  }
}

print("Testing get_odds with match sample...")
odds = get_odds(match_with_odds)
print(f"Result: {odds}")

if odds['home'] and odds['away']:
    print("SUCCESS: Odds extracted.")
else:
    print("FAIL: Odds not extracted.")
