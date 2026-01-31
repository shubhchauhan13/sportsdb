"""
Healer Agent - Self-Repair for Sportsbook

Responsibilities:
- Restart crashed workers
- Switch data sources when blocked
- Run diagnostic scripts
- Apply fixes based on AI reasoning
"""

import os
import sys
import subprocess
import signal
import logging
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core import TogetherAIClient, Agent, Tool, create_tool

import psycopg2

logger = logging.getLogger("HealerAgent")

# =============================================================================
# Configuration
# =============================================================================

DB_CONNECTION_STRING = os.environ.get(
    "DB_CONNECTION_STRING",
    "postgresql://neondb_owner:npg_CI3RX5EphOlT@ep-rapid-moon-ahwmx6r0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Worker process tracking (populated at runtime)
WORKER_PIDS = {}

# Source priority configuration
SOURCE_PRIORITY = {
    "football": ["aiscore", "soccer24", "sofascore"],
    "cricket": ["aiscore", "sofascore", "crex"],
    "basketball": ["aiscore", "sofascore"],
    "tennis": ["aiscore", "sofascore"],
    "table_tennis": ["sofascore", "aiscore"],
    "esports": ["sofascore", "1xbet"],
    "ice_hockey": ["aiscore", "sofascore"],
    "volleyball": ["sofascore", "aiscore"],
}

# Active source overrides (modified by switch_data_source)
ACTIVE_SOURCES = {}


# =============================================================================
# Tool Functions
# =============================================================================

def restart_worker(worker_name: str) -> str:
    """
    Restart a scraper worker by name.
    
    Args:
        worker_name: Name of worker (e.g., 'football', 'cricket', 'esports')
    
    Returns:
        Status message
    """
    worker_script = f"workers/{worker_name}_worker.py"
    full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), worker_script)
    
    if not os.path.exists(full_path):
        return f"Worker script not found: {worker_script}"
    
    # Kill existing worker if running
    if worker_name in WORKER_PIDS:
        old_pid = WORKER_PIDS[worker_name]
        try:
            os.kill(old_pid, signal.SIGTERM)
            logger.info(f"Killed old worker {worker_name} (PID {old_pid})")
        except ProcessLookupError:
            pass  # Already dead
    
    # Start new worker
    try:
        process = subprocess.Popen(
            [sys.executable, "-u", full_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        WORKER_PIDS[worker_name] = process.pid
        logger.info(f"Started worker {worker_name} (PID {process.pid})")
        return f"Worker {worker_name} restarted (PID {process.pid})"
    except Exception as e:
        return f"Failed to restart {worker_name}: {str(e)}"


def switch_data_source(sport: str, new_source: str) -> str:
    """
    Switch the primary data source for a sport.
    
    Args:
        sport: Sport name (e.g., 'football', 'esports')
        new_source: New source to use (e.g., 'sofascore', '1xbet')
    
    Returns:
        Status message
    """
    if sport not in SOURCE_PRIORITY:
        return f"Unknown sport: {sport}"
    
    available = SOURCE_PRIORITY[sport]
    if new_source not in available:
        return f"Source '{new_source}' not available for {sport}. Options: {available}"
    
    old_source = ACTIVE_SOURCES.get(sport, available[0])
    ACTIVE_SOURCES[sport] = new_source
    
    logger.info(f"Switched {sport} source: {old_source} -> {new_source}")
    return f"Switched {sport} from {old_source} to {new_source}"


def run_diagnostic_script(script_name: str) -> str:
    """
    Run a diagnostic script and return its output.
    
    Args:
        script_name: Name of script in sportsdb root (e.g., 'check_staleness.py')
    
    Returns:
        Script output (truncated if too long)
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    script_path = os.path.join(base_dir, script_name)
    
    if not os.path.exists(script_path):
        return f"Script not found: {script_name}"
    
    if not script_name.endswith(".py"):
        return "Only .py scripts allowed"
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        output = result.stdout + result.stderr
        # Truncate if too long
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"Script {script_name} timed out after 60s"
    except Exception as e:
        return f"Script execution failed: {str(e)}"


def query_recent_logs(lines: int = 50) -> str:
    """
    Get recent log entries from scraper output.
    
    Args:
        lines: Number of recent lines to return
    
    Returns:
        Recent log content
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    log_path = os.path.join(base_dir, "scraper_output.log")
    
    if not os.path.exists(log_path):
        return "Log file not found"
    
    try:
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(recent)
    except Exception as e:
        return f"Failed to read logs: {str(e)}"


def clear_stale_matches(sport: str) -> str:
    """
    Clear stale matches for a sport by marking them as finished.
    
    Args:
        sport: Sport name to clear
    
    Returns:
        Number of matches cleared
    """
    table_name = f"live_{sport}"
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        cur = conn.cursor()
        
        # Mark all "live" matches older than 30 min as finished
        cur.execute(f"""
            UPDATE {table_name}
            SET status = 'Finished', is_live = FALSE
            WHERE is_live = TRUE
            AND last_updated < NOW() - INTERVAL '30 minutes'
        """)
        
        cleared = cur.rowcount
        conn.commit()
        conn.close()
        
        return f"Cleared {cleared} stale matches from {sport}"
        
    except Exception as e:
        return f"Failed to clear stale matches: {str(e)}"


def force_refresh_sport(sport: str) -> str:
    """
    Trigger an immediate refresh for a sport via the API.
    
    Args:
        sport: Sport to refresh
    
    Returns:
        Status message
    """
    import requests
    
    api_url = os.environ.get("API_BASE_URL", "http://localhost:8080")
    
    try:
        resp = requests.post(
            f"{api_url}/api/force_refresh",
            params={"sport": sport},
            timeout=10
        )
        if resp.status_code == 200:
            return f"Force refresh queued for {sport}"
        else:
            return f"Force refresh failed: HTTP {resp.status_code}"
    except Exception as e:
        return f"Force refresh failed: {str(e)}"


# =============================================================================
# Healer Agent Class
# =============================================================================

class HealerAgent(Agent):
    """
    Self-repair agent that fixes issues identified by Ops Agent.
    
    Uses AI reasoning to determine the best fix for each issue.
    """
    
    def __init__(self, client: TogetherAIClient, model: str = None):
        super().__init__(client, model)
        self._register_tools()
    
    def _register_tools(self):
        """Register all healer tools."""
        
        self.add_tool(create_tool(
            name="restart_worker",
            description="Restart a crashed or stuck scraper worker",
            parameters={
                "worker_name": {"type": "string", "description": "Worker name (football, cricket, esports, table_tennis)"}
            },
            function=restart_worker
        ))
        
        self.add_tool(create_tool(
            name="switch_data_source",
            description="Switch to a different data source for a sport (use when current source is blocked)",
            parameters={
                "sport": {"type": "string", "description": "Sport name"},
                "new_source": {"type": "string", "description": "New source (sofascore, aiscore, 1xbet, soccer24)"}
            },
            function=switch_data_source
        ))
        
        self.add_tool(create_tool(
            name="run_diagnostic_script",
            description="Run a diagnostic Python script to investigate issues",
            parameters={
                "script_name": {"type": "string", "description": "Script filename (e.g., check_staleness.py)"}
            },
            function=run_diagnostic_script
        ))
        
        self.add_tool(create_tool(
            name="query_recent_logs",
            description="Get recent log entries to understand what went wrong",
            parameters={
                "lines": {"type": "integer", "description": "Number of lines to retrieve (default 50)"}
            },
            function=query_recent_logs
        ))
        
        self.add_tool(create_tool(
            name="clear_stale_matches",
            description="Clear old stale matches from a sport's table",
            parameters={
                "sport": {"type": "string", "description": "Sport to clear stale matches from"}
            },
            function=clear_stale_matches
        ))
        
        self.add_tool(create_tool(
            name="force_refresh_sport",
            description="Force an immediate data refresh for a sport",
            parameters={
                "sport": {"type": "string", "description": "Sport to refresh"}
            },
            function=force_refresh_sport
        ))
    
    def get_system_prompt(self) -> str:
        return """You are the Healer Agent for a live sports betting data platform.

Your job is to FIX issues identified by the Ops Agent.

When given an issue description:
1. First, understand the problem (check logs if needed)
2. Determine the root cause
3. Apply the appropriate fix:
   - If data is stale: try force_refresh first, then restart_worker
   - If source is blocked: switch_data_source
   - If data is corrupted: clear_stale_matches
4. Verify the fix worked

Available diagnostic scripts:
- check_staleness.py: Shows freshness of all sports
- analyze_odds_quality.py: Shows odds coverage
- check_odds_population.py: Detailed odds check
- diagnose_db.py: Database health check

Be surgical - only apply fixes relevant to the issue.
Report what you did and whether it succeeded."""


if __name__ == "__main__":
    # Quick test
    client = TogetherAIClient()
    agent = HealerAgent(client)
    
    # Test with a sample issue
    result = agent.run("Esports data is stale (last update 25 minutes ago). Investigate and fix.")
    print(result)
