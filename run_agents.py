"""
Sportsbook AI Agent Runner

Main entry point that orchestrates all agents and workers.
Run this instead of scraper_service.py to use the multi-agent system.
"""

import os
import sys
import time
import signal
import logging
import threading
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agent_runner.log')
    ]
)
logger = logging.getLogger("AgentRunner")

# =============================================================================
# Configuration
# =============================================================================

# Agent intervals (seconds)
OPS_INTERVAL = int(os.environ.get("OPS_INTERVAL", "60"))
HEALER_INTERVAL = int(os.environ.get("HEALER_INTERVAL", "120"))
HUNTER_INTERVAL = int(os.environ.get("HUNTER_INTERVAL", "300"))

# Workers to spawn
WORKERS = [
    # {"name": "football", "script": "workers/football_worker.py"},
    # {"name": "cricket", "script": "workers/cricket_worker.py"},
    # The main scraper_service.py handles all scraping for now
]

# Shutdown flag
SHUTDOWN_FLAG = False


def signal_handler(signum, frame):
    global SHUTDOWN_FLAG
    logger.info(f"Received signal {signum}. Shutting down...")
    SHUTDOWN_FLAG = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# =============================================================================
# Agent Threads
# =============================================================================

def run_ops_agent():
    """Run the Ops Agent in a loop."""
    from agent_core import TogetherAIClient
    from agents.ops_agent import OpsAgent
    
    logger.info("[OpsAgent] Starting...")
    
    try:
        client = TogetherAIClient()
        agent = OpsAgent(client)
    except Exception as e:
        logger.error(f"[OpsAgent] Failed to initialize: {e}")
        return
    
    # Initial delay to let services start
    time.sleep(10)
    
    while not SHUTDOWN_FLAG:
        try:
            logger.info("[OpsAgent] Running health check...")
            result = agent.run(
                "Perform a complete health check. Check API health, all sports freshness, "
                "and odds coverage for esports and table_tennis. Report issues."
            )
            logger.info(f"[OpsAgent] Result:\n{result}")
        except Exception as e:
            logger.error(f"[OpsAgent] Error: {e}")
        
        # Sleep in chunks to allow quick shutdown
        for _ in range(OPS_INTERVAL):
            if SHUTDOWN_FLAG:
                break
            time.sleep(1)
    
    logger.info("[OpsAgent] Stopped.")


def run_odds_hunter():
    """Run the Odds Hunter Agent in a loop."""
    from agent_core import TogetherAIClient
    from agents.odds_hunter import OddsHunterAgent
    
    logger.info("[OddsHunter] Starting...")
    
    try:
        client = TogetherAIClient()
        agent = OddsHunterAgent(client)
    except Exception as e:
        logger.error(f"[OddsHunter] Failed to initialize: {e}")
        return
    
    # Initial delay
    time.sleep(30)
    
    while not SHUTDOWN_FLAG:
        try:
            logger.info("[OddsHunter] Hunting for odds...")
            result = agent.run(
                "Check odds coverage summary. Hunt odds for the sport with the worst coverage. "
                "Update at least 5 matches if possible."
            )
            logger.info(f"[OddsHunter] Result:\n{result}")
        except Exception as e:
            logger.error(f"[OddsHunter] Error: {e}")
        
        for _ in range(HUNTER_INTERVAL):
            if SHUTDOWN_FLAG:
                break
            time.sleep(1)
    
    logger.info("[OddsHunter] Stopped.")


# =============================================================================
# Worker Process Management
# =============================================================================

WORKER_PROCESSES = {}


def start_worker(name: str, script: str):
    """Start a worker subprocess."""
    if name in WORKER_PROCESSES:
        proc = WORKER_PROCESSES[name]
        if proc.poll() is None:
            logger.info(f"Worker {name} already running (PID {proc.pid})")
            return
    
    script_path = os.path.join(os.path.dirname(__file__), script)
    if not os.path.exists(script_path):
        logger.warning(f"Worker script not found: {script}")
        return
    
    logger.info(f"Starting worker: {name}")
    proc = subprocess.Popen(
        [sys.executable, "-u", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    WORKER_PROCESSES[name] = proc
    logger.info(f"Worker {name} started (PID {proc.pid})")


def stop_all_workers():
    """Stop all worker subprocesses."""
    for name, proc in WORKER_PROCESSES.items():
        if proc.poll() is None:
            logger.info(f"Stopping worker: {name}")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def start_scraper_service():
    """
    Start the original scraper_service.py as a subprocess.
    This provides the API server and scraping loops.
    """
    script_path = os.path.join(os.path.dirname(__file__), "scraper_service.py")
    if not os.path.exists(script_path):
        logger.error("scraper_service.py not found!")
        return None
    
    logger.info("Starting scraper_service.py...")
    proc = subprocess.Popen(
        [sys.executable, "-u", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    logger.info(f"scraper_service.py started (PID {proc.pid})")
    return proc


# =============================================================================
# Main
# =============================================================================

def main():
    logger.info("=" * 60)
    logger.info("SPORTSBOOK AI AGENT RUNNER")
    logger.info("=" * 60)
    logger.info(f"Together AI Key: {'Set' if os.environ.get('TOGETHER_API_KEY') else 'NOT SET'}")
    logger.info(f"Ops Interval: {OPS_INTERVAL}s")
    logger.info(f"Hunter Interval: {HUNTER_INTERVAL}s")
    logger.info("=" * 60)
    
    # Start the scraper service (provides API + scraping)
    scraper_proc = start_scraper_service()
    
    # Start workers (if defined)
    for w in WORKERS:
        start_worker(w["name"], w["script"])
    
    # Start agent threads
    threads = []
    
    ops_thread = threading.Thread(target=run_ops_agent, name="OpsAgent", daemon=True)
    ops_thread.start()
    threads.append(ops_thread)
    
    hunter_thread = threading.Thread(target=run_odds_hunter, name="OddsHunter", daemon=True)
    hunter_thread.start()
    threads.append(hunter_thread)
    
    logger.info("All agents started. Press Ctrl+C to stop.")
    
    # Main loop - monitor and keep alive
    try:
        while not SHUTDOWN_FLAG:
            # Check if scraper service is still running
            if scraper_proc and scraper_proc.poll() is not None:
                logger.warning("scraper_service.py died! Restarting...")
                scraper_proc = start_scraper_service()
            
            # Check workers
            for w in WORKERS:
                proc = WORKER_PROCESSES.get(w["name"])
                if proc and proc.poll() is not None:
                    logger.warning(f"Worker {w['name']} died! Restarting...")
                    start_worker(w["name"], w["script"])
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    
    # Cleanup
    logger.info("Shutting down...")
    global SHUTDOWN_FLAG
    SHUTDOWN_FLAG = True
    
    stop_all_workers()
    
    if scraper_proc:
        scraper_proc.terminate()
        try:
            scraper_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            scraper_proc.kill()
    
    # Wait for threads
    for t in threads:
        t.join(timeout=5)
    
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
