#!/usr/bin/env python3
"""
AI Red Team Project
"""

import os
import json
import asyncio
import argparse
import re
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.evaluation.red_team import RedTeam, RiskCategory, AttackStrategy

# Import target classes from targets folder
from targets.mcs_agent_callback import McsAgentCallbackTarget, McsAgentConfig


# ---------------------------------------------------------------------------
# Load Environment Variables and Configuration
# ---------------------------------------------------------------------------

def load_environment_variables():
    """Load environment variables from .env file."""
    load_dotenv()
    print("Environment variables loaded from .env file")


def substitute_env_vars(text: str) -> str:
    """Replace ${VAR_NAME} placeholders with environment variable values."""
    def replace_func(match):
        var_name = match.group(1)
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Environment variable '{var_name}' not found")
        return value
    
    return re.sub(r'\$\{([^}]+)\}', replace_func, text)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file and substitute environment variables."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load raw JSON content
    with open(config_path, 'r') as f:
        raw_content = f.read()
    
    # Substitute environment variables
    processed_content = substitute_env_vars(raw_content)
    
    # Parse JSON
    return json.loads(processed_content)


def create_mcs_agent_config(config_data: Dict[str, Any]) -> Optional[McsAgentConfig]:
    """Create MCS Agent configuration if available."""
    mcs_config = config_data.get("mcs_agent", {})
    if not all([mcs_config.get("tenant_id"), mcs_config.get("app_client_id"),
                mcs_config.get("environment_id"), mcs_config.get("agent_identifier")]):
        return None
    
    return McsAgentConfig(
        tenant_id=mcs_config["tenant_id"],
        app_client_id=mcs_config["app_client_id"],
        environment_id=mcs_config["environment_id"],
        agent_identifier=mcs_config["agent_identifier"]
    )


# ---------------------------------------------------------------------------
# Create Target Based on Configuration
# ---------------------------------------------------------------------------

def create_target(target_type: str, mcs_agent_config: Optional[McsAgentConfig]):
    """Create target instance based on type."""
    if target_type == "mcs_agent_callback":
        if not mcs_agent_config:
            raise ValueError("MCS Agent config is required for MCS Agent callback target")
        target = McsAgentCallbackTarget(mcs_agent_config)
        return target.get_target()
    else:
        raise ValueError(f"Unsupported target type: {target_type}. Only 'mcs_agent_callback' is supported.")


# ---------------------------------------------------------------------------
# Parse Risk Categories and Attack Strategies
# ---------------------------------------------------------------------------

def parse_risk_categories(category_strings: List[str]) -> List[RiskCategory]:
    """Convert category strings to RiskCategory enums."""
    risk_categories = []
    for category_str in category_strings:
        risk_categories.append(getattr(RiskCategory, category_str))
    return risk_categories


def parse_attack_strategies(strategy_strings: List[str]) -> List[AttackStrategy]:
    """Convert strategy strings to AttackStrategy enums."""
    attack_strategies = []
    for strategy_str in strategy_strings:
        if strategy_str.upper() == "EASY":
            attack_strategies.append(AttackStrategy.EASY)
        elif strategy_str.upper() == "MODERATE":
            attack_strategies.append(AttackStrategy.MODERATE)
        elif strategy_str.upper() == "DIFFICULT":
            attack_strategies.append(AttackStrategy.DIFFICULT)
        else:
            attack_strategies.append(getattr(AttackStrategy, strategy_str))
    return attack_strategies


# ---------------------------------------------------------------------------
# Red Team Scan
# ---------------------------------------------------------------------------

def create_red_team(
    project_endpoint: str, 
    risk_categories: List[RiskCategory], 
    num_objectives: int,
    custom_prompts_path: Optional[str] = None
) -> RedTeam:
    """Create RedTeam instance with optional custom prompts."""
    credential = DefaultAzureCredential()
    
    # If custom prompts path is provided and file exists, use custom prompts
    if custom_prompts_path and os.path.exists(custom_prompts_path):
        print(f"Using custom prompts from: {custom_prompts_path}")
        return RedTeam(
            azure_ai_project=project_endpoint,
            credential=credential,
            custom_attack_seed_prompts=custom_prompts_path,
        )
    
    # Otherwise use standard risk categories
    print(f"Using standard risk categories with {num_objectives} objectives")
    return RedTeam(
        azure_ai_project=project_endpoint,
        credential=credential,
        risk_categories=risk_categories,
        num_objectives=num_objectives,
    )

async def run_red_team_scan(target, scan_name: str, attack_strategies: List[AttackStrategy], red_team: RedTeam):
    """Run the red team scan."""
    print(f"Starting red team scan: {scan_name}")
    
    # Run the scan (reports will be auto-generated)
    result = await red_team.scan(
        target=target,
        scan_name=scan_name,
        attack_strategies=attack_strategies
    )
    
    print(f"Red team scan completed: {scan_name}")
    print(f"Scan results are automatically saved in the scan directory.")
    
    return result


# ---------------------------------------------------------------------------
# Command Line Interface
# ---------------------------------------------------------------------------

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="AI Red Team Evaluation Tool for Microsoft Copilot Studio Agents",
        epilog="""
Example:
  python red_team_scan.py --config config/mcs_agent_callback.json
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to configuration JSON file"
    )
    
    args = parser.parse_args()
    
    print("AI Red Team Evaluation Tool")
    print("=" * 40)
    print(f"Using configuration file: {args.config}")
    
    try:
        # Step 1: Load environment variables from .env file
        load_environment_variables()
        
        # Step 2: Load configuration from JSON file (with env var substitution)
        config_data = load_config(args.config)
        
        # Step 3: Get target type from config file
        target_type = config_data.get("target", {}).get("type")
        if not target_type:
            print("Error: Target type not specified in config file")
            return
        
        print(f"Target type from config: {target_type}")
        
        # Step 4: Extract configuration sections
        azure_ai_project = config_data.get("azure_ai_project", {})
        project_endpoint = azure_ai_project.get("project_endpoint")
        
        red_team_config = config_data.get("red_team", {})
        scan_config = config_data.get("scan", {})
        
        # Step 5: Validate required settings
        if not project_endpoint:
            print("Error: Azure AI Project endpoint is required")
            return
        
        print("Configuration loaded successfully")
        print(f"Project endpoint: {project_endpoint}")
        
        # Step 6: Parse risk categories and attack strategies
        risk_categories = parse_risk_categories(red_team_config.get("risk_categories", ["Violence", "HateUnfairness"]))
        attack_strategies = parse_attack_strategies(red_team_config.get("attack_strategies", ["Flip"]))
        num_objectives = red_team_config.get("num_objectives", 1)
        custom_prompts_path = red_team_config.get("custom_prompts_path", "")
        scan_name = scan_config.get("name", "RedTeamScan")
        
        # Step 7: Create MCS Agent config
        mcs_agent_config = create_mcs_agent_config(config_data)
        
        # Step 8: Create RedTeam instance (with optional custom prompts)
        red_team = create_red_team(
            project_endpoint, 
            risk_categories, 
            num_objectives,
            custom_prompts_path if custom_prompts_path else None
        )
        
        # Step 9: Create target
        target = create_target(target_type, mcs_agent_config)
        
        # Step 10: Run the red team scan
        result = await run_red_team_scan(target, scan_name, attack_strategies, red_team)
        
        print("\n" + "=" * 40)
        print("Red team evaluation completed successfully!")
        
        return result
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
    