"""
Ops Agent - Central Orchestrator for Sportsbook

Responsibilities:
- Monitor API health
- Check data freshness across sports
- Delegate issues to Healer Agent
- Send Telegram alerts
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core import TogetherAIClient, Agent, Tool, create_tool

import requests
import psycopg2

logger = logging.getLogger("OpsAgent")

# =============================================================================
# Configuration
# =============================================================================

DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING",
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SPORTS_TABLES = [
    "live_football", "live_cricket", "live_basketball", "live_tennis",
    "live_table_tennis", "live_ice_hockey", "live_esports", "live_volleyball",
    "live_baseball", "live_badminton", "live_american_football", "live_handball",
    "live_water_polo", "live_snooker", "live_rugby", "live_motorsport"
]

STALE_THRESHOLD_MINUTES = 10


# =============================================================================
# Tool Functions
# =============================================================================

def check_api_health() -> str:
    """Check the /health endpoint of the API server."""
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "unknown")
            blocked = data.get("blocked_sources", [])
            if blocked:
                return f"API Status: {status} (WARNING: {len(blocked)} blocked sources: {blocked})"
            return f"API Status: {status}"
        else:
            return f"API UNHEALTHY: HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return "API UNREACHABLE: Connection refused"
    except Exception as e:
        return f"API CHECK FAILED: {str(e)}"


def check_data_freshness(sport: str) -> str:
    """
    Check freshness of a specific sport's data.
    
    Args:
        sport: Sport name (e.g., 'football', 'cricket')
    
    Returns:
        Freshness status string
    """
    table_name = f"live_{sport}"
    if table_name not in SPORTS_TABLES:
        return f"Unknown sport: {sport}"
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        cur.execute(f"SELECT MAX(last_updated), COUNT(*) FROM {table_name} WHERE is_live = TRUE")
        row = cur.fetchone()
        last_updated, live_count = row[0], row[1]
        
        conn.close()
        
        if not last_updated:
            return f"{sport}: No live matches (0 rows)"
        
        # Calculate staleness
        now = datetime.now(last_updated.tzinfo) if last_updated.tzinfo else datetime.now()
        delta_seconds = (now - last_updated).total_seconds()
        delta_minutes = int(delta_seconds / 60)
        
        if delta_minutes > STALE_THRESHOLD_MINUTES:
            return f"{sport}: STALE ({delta_minutes}m ago, {live_count} live matches)"
        else:
            return f"{sport}: FRESH ({delta_minutes}m ago, {live_count} live matches)"
            
    except Exception as e:
        return f"{sport}: DB ERROR - {str(e)}"


def check_all_sports_freshness() -> str:
    """Check freshness of all sports at once."""
    results = []
    stale_sports = []
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        for table in SPORTS_TABLES:
            sport = table.replace("live_", "")
            try:
                cur.execute(f"SELECT MAX(last_updated), COUNT(*) FROM {table} WHERE is_live = TRUE")
                row = cur.fetchone()
                last_updated, live_count = row[0], row[1]
                
                if not last_updated or live_count == 0:
                    results.append(f"{sport}: EMPTY")
                    continue
                
                now = datetime.now(last_updated.tzinfo) if last_updated.tzinfo else datetime.now()
                delta_minutes = int((now - last_updated).total_seconds() / 60)
                
                if delta_minutes > STALE_THRESHOLD_MINUTES:
                    results.append(f"{sport}: STALE ({delta_minutes}m)")
                    stale_sports.append(sport)
                else:
                    results.append(f"{sport}: OK ({live_count} live)")
                    
            except Exception as e:
                results.append(f"{sport}: ERROR")
        
        conn.close()
        
    except Exception as e:
        return f"DB Connection Failed: {str(e)}"
    
    summary = f"Checked {len(SPORTS_TABLES)} sports. Stale: {len(stale_sports)}"
    if stale_sports:
        summary += f" ({', '.join(stale_sports)})"
    
    return summary + "\n" + "\n".join(results)


def check_odds_coverage(sport: str) -> str:
    """
    Check odds coverage for a specific sport.
    
    Returns percentage of live matches with valid odds.
    """
    table_name = f"live_{sport}"
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        # Total live matches
        cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE is_live = TRUE")
        total = cur.fetchone()[0]
        
        if total == 0:
            conn.close()
            return f"{sport}: No live matches to check odds"
        
        # Matches with valid odds (other_odds is not null/empty)
        cur.execute(f"""
            SELECT COUNT(*) FROM {table_name} 
            WHERE is_live = TRUE 
            AND other_odds IS NOT NULL 
            AND other_odds::text != '{{}}'
            AND other_odds::text != 'null'
        """)
        with_odds = cur.fetchone()[0]
        
        conn.close()
        
        coverage = round((with_odds / total) * 100, 1)
        status = "GOOD" if coverage > 80 else "NEEDS_ATTENTION" if coverage > 50 else "CRITICAL"
        
        return f"{sport}: {coverage}% odds coverage ({with_odds}/{total} matches) - {status}"
        
    except Exception as e:
        return f"{sport}: Odds check failed - {str(e)}"


def send_telegram_alert(message: str) -> str:
    """Send an alert message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "Telegram not configured"
    
    try:
        chat_ids = [x.strip() for x in TELEGRAM_CHAT_ID.split(",")]
        sent_count = 0
        
        for chat_id in chat_ids:
            if not chat_id:
                continue
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                sent_count += 1
        
        return f"Telegram sent to {sent_count} recipients"
        
    except Exception as e:
        return f"Telegram failed: {str(e)}"


def delegate_to_healer(issue_description: str) -> str:
    """
    Delegate an issue to the Healer Agent.
    
    In v1, this just logs the issue. In v2, it will actually invoke HealerAgent.
    """
    logger.warning(f"HEALER DELEGATION: {issue_description}")
    # TODO: Actually invoke HealerAgent.run(issue_description)
    return f"Issue delegated to Healer: {issue_description}"


# =============================================================================
# Ops Agent Class
# =============================================================================

class OpsAgent(Agent):
    """
    Central orchestrator agent for the sportsbook.
    
    Monitors health, freshness, and odds coverage.
    Delegates issues to Healer Agent.
    """
    
    def __init__(self, client: TogetherAIClient, model: str = None):
        super().__init__(client, model)
        self._register_tools()
    
    def _register_tools(self):
        """Register all ops tools."""
        
        self.add_tool(create_tool(
            name="check_api_health",
            description="Check if the API server is healthy and responding",
            parameters={},
            function=check_api_health
        ))
        
        self.add_tool(create_tool(
            name="check_data_freshness",
            description="Check how fresh the data is for a specific sport",
            parameters={
                "sport": {"type": "string", "description": "Sport name (e.g., 'football', 'cricket', 'esports')"}
            },
            function=check_data_freshness
        ))
        
        self.add_tool(create_tool(
            name="check_all_sports_freshness",
            description="Check freshness of ALL sports at once - use this for a complete overview",
            parameters={},
            function=check_all_sports_freshness
        ))
        
        self.add_tool(create_tool(
            name="check_odds_coverage",
            description="Check what percentage of live matches have odds for a sport",
            parameters={
                "sport": {"type": "string", "description": "Sport name to check odds coverage for"}
            },
            function=check_odds_coverage
        ))
        
        self.add_tool(create_tool(
            name="send_telegram_alert",
            description="Send an alert message to Telegram. Use for important issues or status updates.",
            parameters={
                "message": {"type": "string", "description": "The alert message to send (markdown supported)"}
            },
            function=send_telegram_alert
        ))
        
        self.add_tool(create_tool(
            name="delegate_to_healer",
            description="Delegate an issue to the Healer Agent to fix. Use when you detect a problem that needs fixing.",
            parameters={
                "issue_description": {"type": "string", "description": "Description of the issue that needs fixing"}
            },
            function=delegate_to_healer
        ))
    
    def get_system_prompt(self) -> str:
        return """You are the Ops Agent for a live sports betting data platform.

Your responsibilities:
1. Monitor system health using available tools
2. Check data freshness across all sports
3. Identify sports with poor odds coverage
4. Alert the team via Telegram for critical issues
5. Delegate fixes to the Healer Agent

When you receive a task:
1. First check overall API health
2. Then check all sports freshness
3. For any stale or problematic sports, check odds coverage
4. If issues found, delegate to healer AND send Telegram alert
5. Provide a concise summary of system status

Be proactive about finding issues. A stale sport (>10 min old) is a problem.
Poor odds coverage (<50%) is a problem, especially for esports and table_tennis.

Always end with a clear status summary."""


# =============================================================================
# Main Loop
# =============================================================================

def run_ops_loop(interval_seconds: int = 60):
    """
    Run the Ops Agent in a loop.
    
    Args:
        interval_seconds: How often to run health checks
    """
    logger.info("Starting Ops Agent loop...")
    
    client = TogetherAIClient()
    agent = OpsAgent(client)
    
    while True:
        try:
            logger.info("=" * 50)
            logger.info("Running Ops Check...")
            
            result = agent.run("Perform a complete health check of the sportsbook system. Check API health, all sports freshness, and odds coverage for any problematic sports.")
            
            logger.info(f"Ops Check Result:\n{result}")
            
        except Exception as e:
            logger.error(f"Ops loop error: {e}")
        
        logger.info(f"Sleeping for {interval_seconds}s...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Quick test
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    
    if args.loop:
        run_ops_loop(args.interval)
    elif args.once:
        client = TogetherAIClient()
        agent = OpsAgent(client)
        result = agent.run("Perform a quick health check of the system.")
        print(result)
    else:
        print("Use --loop for continuous mode or --once for single check")
