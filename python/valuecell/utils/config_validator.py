"""
Configuration validation utility for pre-flight checks

This module provides functions to validate agent configurations before startup,
checking for missing API keys, misconfigured providers, and other issues.
"""

import logging
from typing import List, Tuple

from valuecell.config.manager import ConfigManager, get_config_manager

logger = logging.getLogger(__name__)


def validate_agent_config(agent_name: str) -> Tuple[bool, List[str]]:
    """
    Validate agent configuration before startup

    Checks:
    - Primary model provider availability
    - Embedding provider availability (if configured)
    - API keys are set for required providers

    Args:
        agent_name: Agent name to validate (e.g., "ResearchAgent", "AutoTradingAgent")

    Returns:
        Tuple of (is_valid, warnings) where:
        - is_valid: True if no critical issues found
        - warnings: List of warning messages about configuration issues

    Example:
        >>> is_valid, warnings = validate_agent_config("ResearchAgent")
        >>> if warnings:
        ...     for warning in warnings:
        ...         print(f"Warning: {warning}")
    """
    warnings: List[str] = []
    config_manager: ConfigManager = get_config_manager()

    try:
        agent_config = config_manager.get_agent_config(agent_name)

        if not agent_config:
            warnings.append(f"Agent configuration not found: {agent_name}")
            return False, warnings

        if not agent_config.enabled:
            warnings.append(f"Agent is disabled: {agent_name}")
            return False, warnings

        # Check primary model provider
        provider = agent_config.primary_model.provider
        is_valid, error = config_manager.validate_provider(provider)
        if not is_valid:
            warnings.append(f"Primary provider '{provider}' unavailable: {error}")

        # Check embedding provider if configured
        if agent_config.embedding_model:
            emb_provider = agent_config.embedding_model.provider
            is_valid, error = config_manager.validate_provider(emb_provider)
            if not is_valid:
                warnings.append(
                    f"Embedding provider '{emb_provider}' unavailable: {error}. "
                    "Will attempt fallback to other providers."
                )

        return len(warnings) == 0, warnings

    except Exception as e:
        logger.error(f"Error validating agent config for {agent_name}: {e}")
        warnings.append(f"Validation error: {str(e)}")
        return False, warnings


def validate_all_agents() -> dict[str, Tuple[bool, List[str]]]:
    """
    Validate all configured agents

    Returns:
        Dictionary mapping agent names to (is_valid, warnings) tuples

    Example:
        >>> results = validate_all_agents()
        >>> for agent_name, (is_valid, warnings) in results.items():
        ...     print(f"{agent_name}: {'OK' if is_valid else 'WARNINGS'}")
    """
    config_manager = get_config_manager()
    results = {}

    try:
        agent_names = config_manager.loader.list_agents()
        for agent_name in agent_names:
            results[agent_name] = validate_agent_config(agent_name)
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        # Return empty dict on error rather than crashing
        return {}

    return results


def print_validation_report(agent_name: str = None) -> None:
    """
    Print a human-readable validation report

    Args:
        agent_name: Specific agent to validate, or None for all agents

    Example:
        >>> print_validation_report("ResearchAgent")
        >>> # or
        >>> print_validation_report()  # All agents
    """
    if agent_name:
        is_valid, warnings = validate_agent_config(agent_name)
        status = "✅" if is_valid else "⚠️"
        print(f"{status} {agent_name}")
        if warnings:
            for warning in warnings:
                print(f"   - {warning}")
    else:
        results = validate_all_agents()
        for agent_name, (is_valid, warnings) in results.items():
            status = "✅" if is_valid else "⚠️"
            print(f"{status} {agent_name}")
            if warnings:
                for warning in warnings:
                    print(f"   - {warning}")


if __name__ == "__main__":
    """CLI entry point for validation"""
    import sys

    agent_name = sys.argv[1] if len(sys.argv) > 1 else None
    print_validation_report(agent_name)

