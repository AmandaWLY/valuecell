"""
Interactive agent launcher script.
Allows users to select an agent from available options and launch it using uv.
"""

import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict

# Mapping from agent name to analyst key (for ai-hedge-fund agents)
MAP_NAME_ANALYST: Dict[str, str] = {
    "AswathDamodaranAgent": "aswath_damodaran",
    "BenGrahamAgent": "ben_graham",
    "BillAckmanAgent": "bill_ackman",
    "CathieWoodAgent": "cathie_wood",
    "CharlieMungerAgent": "charlie_munger",
    "FundamentalsAnalystAgent": "fundamentals_analyst",
    "MichaelBurryAgent": "michael_burry",
    "MohnishPabraiAgent": "mohnish_pabrai",
    "PeterLynchAgent": "peter_lynch",
    "PhilFisherAgent": "phil_fisher",
    "RakeshJhunjhunwalaAgent": "rakesh_jhunjhunwala",
    "SentimentAnalystAgent": "sentiment_analyst",
    "StanleyDruckenmillerAgent": "stanley_druckenmiller",
    "TechnicalAnalystAgent": "technical_analyst",
    "ValuationAnalystAgent": "valuation_analyst",
    "WarrenBuffettAgent": "warren_buffett",
}
TRADING_AGENTS_NAME = "TradingAgents"
RESEARCH_AGENT_NAME = "ResearchAgent"
AUTO_TRADING_AGENT_NAME = "AutoTradingAgent"
NEWS_AGENT_NAME = "NewsAgent"
# AGENTS = list(MAP_NAME_ANALYST.keys()) + [
#     TRADING_AGENTS_NAME,
#     RESEARCH_AGENT_NAME,
#     AUTO_TRADING_AGENT_NAME,
# ]
AGENTS = [RESEARCH_AGENT_NAME, AUTO_TRADING_AGENT_NAME, NEWS_AGENT_NAME]

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
PYTHON_DIR = PROJECT_DIR / "python"
ENV_PATH = PROJECT_DIR / ".env"

# Convert paths to POSIX format (forward slashes) for cross-platform compatibility
# as_posix() works on both Windows and Unix systems
# Keep unquoted versions for Python path operations and quoted versions for shell commands
PROJECT_DIR_STR = PROJECT_DIR.as_posix()
PYTHON_DIR_STR = PYTHON_DIR.as_posix()
ENV_PATH_STR = ENV_PATH.as_posix()

# Create properly quoted versions for shell commands using shlex.quote()
PROJECT_DIR_QUOTED = shlex.quote(PROJECT_DIR_STR)
PYTHON_DIR_QUOTED = shlex.quote(PYTHON_DIR_STR)
ENV_PATH_QUOTED = shlex.quote(ENV_PATH_STR)

AUTO_TRADING_ENV_OVERRIDES = {
    "AUTO_TRADING_EXCHANGE": os.getenv("AUTO_TRADING_EXCHANGE"),
}
AUTO_TRADING_ENV_PREFIX = " ".join(
    f"{key}={value}"
    for key, value in AUTO_TRADING_ENV_OVERRIDES.items()
    if value not in (None, "")
)
if AUTO_TRADING_ENV_PREFIX:
    AUTO_TRADING_ENV_PREFIX = f"{AUTO_TRADING_ENV_PREFIX} "

# Mapping from agent name to launch command
# Use quoted versions for shell commands and relative paths for .env to avoid issues with spaces
MAP_NAME_COMMAND: Dict[str, str] = {}
for name, analyst in MAP_NAME_ANALYST.items():
    MAP_NAME_COMMAND[name] = (
        f'cd {PYTHON_DIR_QUOTED}/third_party/ai-hedge-fund && uv run --env-file ../../../.env -m adapter --analyst {analyst}'
    )
MAP_NAME_COMMAND[TRADING_AGENTS_NAME] = (
    f'cd {PYTHON_DIR_QUOTED}/third_party/TradingAgents && uv run --env-file ../../../.env -m adapter'
)
MAP_NAME_COMMAND[RESEARCH_AGENT_NAME] = (
    f'cd {PYTHON_DIR_QUOTED} && uv run --env-file ../.env -m valuecell.agents.research_agent'
)
MAP_NAME_COMMAND[AUTO_TRADING_AGENT_NAME] = (
    f'{AUTO_TRADING_ENV_PREFIX}cd {PYTHON_DIR_QUOTED} && uv run --env-file ../.env -m valuecell.agents.auto_trading_agent'
)
MAP_NAME_COMMAND[NEWS_AGENT_NAME] = (
    f'cd {PYTHON_DIR_QUOTED} && uv run --env-file ../.env -m valuecell.agents.news_agent'
)
BACKEND_COMMAND = (
    f'cd {PYTHON_DIR_QUOTED} && uv run --env-file ../.env -m valuecell.server.main'
)
FRONTEND_URL = "http://localhost:1420"


def check_envfile_is_set():
    if not ENV_PATH.exists():
        print(
            f".env file not found at {ENV_PATH}. Please create it with necessary environment variables. "
            "check python/.env.example for reference."
        )
        exit(1)


def validate_agents_before_launch(agents: list[str]) -> bool:
    """Validate agent configurations before starting
    
    Args:
        agents: List of agent names to validate
        
    Returns:
        True if all agents are valid, False otherwise
    """
    try:
        from valuecell.utils.config_validator import validate_agent_config
        
        all_valid = True
        for agent_name in agents:
            try:
                is_valid, warnings = validate_agent_config(agent_name)
                if warnings:
                    print(f"⚠️  {agent_name} configuration warnings:")
                    for warning in warnings:
                        print(f"   - {warning}")
                    print()
                    if not is_valid:
                        all_valid = False
            except Exception as e:
                print(f"❌ Failed to validate {agent_name}: {e}")
                all_valid = False
        
        return all_valid
    except ImportError as e:
        print(f"⚠️  Could not import config validator: {e}")
        print("   Skipping validation checks...")
        return True
    except Exception as e:
        print(f"⚠️  Error during validation: {e}")
        print("   Continuing with launch...")
        return True


def main():
    check_envfile_is_set()
    
    # Validate agent configurations before launch
    print("Validating agent configurations...")
    validate_agents_before_launch(AGENTS)
    print()
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_dir = f"{PROJECT_DIR_STR}/logs/{timestamp}"

    # Use questionary multi-select to allow choosing multiple agents
    # selected_agents = questionary.checkbox(
    #     "Choose agents to launch (use space to select, enter to confirm):",
    #     choices=AGENTS,
    # ).ask()
    selected_agents = AGENTS

    if not selected_agents:
        print("No agents selected.")
        exit(1)

    os.makedirs(log_dir, exist_ok=True)
    print(f"Logs will be saved to {log_dir}/")

    processes = []
    logfiles = []
    for selected_agent in selected_agents:
        logfile_path = f"{log_dir}/{selected_agent}.log"
        print(f"Starting agent: {selected_agent} - output to {logfile_path}")

        # Open logfile for writing
        logfile = open(logfile_path, "w")
        logfiles.append(logfile)

        # Launch command using Popen with output redirected to logfile
        process = subprocess.Popen(
            MAP_NAME_COMMAND[selected_agent], shell=True, stdout=logfile, stderr=logfile
        )
        processes.append(process)
    print("All agents launched. Waiting for tasks...")

    for selected_agent in selected_agents:
        print(
            f"You can monitor {selected_agent} logs at {log_dir}/{selected_agent}.log or chat on: {FRONTEND_URL}/agent/{selected_agent}"
        )

    # Launch backend
    logfile_path = f"{log_dir}/backend.log"
    print(f"Starting backend - output to {logfile_path}")
    print(f"Frontend available at {FRONTEND_URL}")
    logfile = open(logfile_path, "w")
    logfiles.append(logfile)
    process = subprocess.Popen(
        BACKEND_COMMAND, shell=True, stdout=logfile, stderr=logfile
    )
    processes.append(process)

    for process in processes:
        process.wait()
    for logfile in logfiles:
        logfile.close()
    print(f"All agents finished. Check {log_dir}/ for output.")


if __name__ == "__main__":
    main()
