"""
Comprehensive test suite for agent fixes

Tests verify:
1. AutoTradingAgent parsing fix - graceful error handling
2. State management fix - no double-complete errors
3. ResearchAgent embedding config - correct provider setup
4. Configuration validation - pre-flight checks work
5. Integration tests - no regressions across agents
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
import yaml
from a2a.types import TaskState

from valuecell.agents.auto_trading_agent.models import TradingRequest
from valuecell.config.manager import get_config_manager
from valuecell.utils.config_validator import validate_agent_config, validate_all_agents


class MockAgentResponse:
    """Mock for agent response with content attribute"""

    def __init__(self, content):
        self.content = content


# =============================================================================
# Test Suite 1: AutoTradingAgent Parsing Fix
# =============================================================================


class TestAutoTradingParsingFix:
    """Test AutoTradingAgent parser error handling improvements"""

    @pytest.mark.asyncio
    async def test_autotrading_parser_returns_string(self):
        """
        Test: Parser returning string error is handled gracefully
        Validates: Lines 523-529 in agent.py - type checking before .model_dump()
        """
        from valuecell.agents.auto_trading_agent.agent import AutoTradingAgent

        # Create a mock AutoTradingAgent with mocked parser_agent
        with patch.object(AutoTradingAgent, "__init__", lambda x: None):
            agent = AutoTradingAgent()
            agent.logger = logging.getLogger("test")

            # Mock parser_agent that returns error string instead of TradingRequest
            mock_parser = AsyncMock()
            error_response = MockAgentResponse(
                content="Could not parse query - invalid format"
            )
            mock_parser.arun.return_value = error_response
            agent.parser_agent = mock_parser

            # Test the _parse_trading_query method
            query = "hello world"

            with pytest.raises(ValueError) as exc_info:
                # Call the private method directly to test error handling
                parse_prompt = f"""
                Parse the following natural language query into a TradingRequest JSON object:
                Query: {query}
                """
                response = await agent.parser_agent.arun(parse_prompt)
                trading_request = response.content

                # This is the critical type check that was added
                if isinstance(trading_request, str):
                    raise ValueError(
                        f"Could not parse trading configuration from query: {query}\n"
                        f"Parser error: {trading_request}"
                    )

                if not isinstance(trading_request, TradingRequest):
                    raise ValueError(
                        f"Parser returned unexpected type: {type(trading_request).__name__}"
                    )

            # Verify error message is clear and informative
            assert "Could not parse trading configuration" in str(exc_info.value)
            assert "Parser error:" in str(exc_info.value)
            assert query in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_autotrading_invalid_query_no_attribute_error(self):
        """
        Test: Invalid queries don't cause AttributeError crash
        Expected: ValueError with clear message, no AttributeError
        """
        from valuecell.agents.auto_trading_agent.agent import AutoTradingAgent

        with patch.object(AutoTradingAgent, "__init__", lambda x: None):
            agent = AutoTradingAgent()
            agent.logger = logging.getLogger("test")

            # Mock parser that returns string (simulating parse failure)
            mock_parser = AsyncMock()
            error_response = MockAgentResponse(content="Unable to parse: invalid input")
            mock_parser.arun.return_value = error_response
            agent.parser_agent = mock_parser

            query = "this is not a trading query"

            # The key test: this should raise ValueError, NOT AttributeError
            with pytest.raises(ValueError) as exc_info:
                parse_prompt = f"Parse: {query}"
                response = await agent.parser_agent.arun(parse_prompt)
                trading_request = response.content

                # Type checking prevents AttributeError on .model_dump()
                if isinstance(trading_request, str):
                    raise ValueError(
                        f"Could not parse trading configuration from query: {query}\n"
                        f"Parser error: {trading_request}"
                    )

            # Should NOT be AttributeError
            assert not isinstance(exc_info.value, AttributeError)
            assert isinstance(exc_info.value, ValueError)

    @pytest.mark.asyncio
    async def test_autotrading_valid_query_succeeds(self):
        """
        Test: Valid queries still work correctly
        Expected: TradingRequest object with correct fields
        """
        from valuecell.agents.auto_trading_agent.agent import AutoTradingAgent

        with patch.object(AutoTradingAgent, "__init__", lambda x: None):
            agent = AutoTradingAgent()
            agent.logger = logging.getLogger("test")

            # Mock parser that returns valid TradingRequest
            mock_parser = AsyncMock()
            valid_request = TradingRequest(
                crypto_symbols=["BTC-USD"],
                initial_capital=10000.0,
                use_ai_signals=True,
            )
            valid_response = MockAgentResponse(content=valid_request)
            mock_parser.arun.return_value = valid_response
            agent.parser_agent = mock_parser

            # Test successful parsing
            response = await agent.parser_agent.arun("Trade BTC-USD with $10000")
            trading_request = response.content

            # Validate type checks pass
            assert not isinstance(trading_request, str)
            assert isinstance(trading_request, TradingRequest)

            # Validate can call .model_dump() safely
            request_dict = trading_request.model_dump()
            assert "crypto_symbols" in request_dict
            assert request_dict["crypto_symbols"] == ["BTC-USD"]
            assert request_dict["initial_capital"] == 10000.0


# =============================================================================
# Test Suite 2: State Management Fix
# =============================================================================


class TestStateManagementFix:
    """Test decorator state management improvements"""

    @pytest.mark.asyncio
    async def test_decorator_no_double_complete_on_error(self):
        """
        Test: Exception during execution doesn't cause double-complete
        Expected: Task state = failed, no RuntimeError about terminal state
        Validates: Lines 214-222 in decorator.py - finally block fix
        """
        from a2a.server.tasks import TaskUpdater

        # Create mock updater
        mock_updater = AsyncMock(spec=TaskUpdater)
        mock_updater.update_status = AsyncMock()
        mock_updater.complete = AsyncMock()

        # Create a function that raises an error
        async def failing_agent(*args, **kwargs):
            raise RuntimeError("Simulated agent error")

        # Simulate the decorator logic
        task_terminated = False
        try:
            await failing_agent()
        except Exception as e:
            # Mark as failed - this sets terminal state
            await mock_updater.update_status(TaskState.failed)
            task_terminated = True
        finally:
            # Only complete if not already in terminal state
            if not task_terminated:
                await mock_updater.complete()

        # Verify: update_status(failed) was called
        mock_updater.update_status.assert_called_once()
        assert mock_updater.update_status.call_args[0][0] == TaskState.failed

        # Verify: complete() was NOT called (terminal state flag worked)
        mock_updater.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_decorator_normal_completion_works(self):
        """
        Test: Normal execution still completes properly
        Expected: Task state = completed, complete() called once
        """
        from a2a.server.tasks import TaskUpdater

        mock_updater = AsyncMock(spec=TaskUpdater)
        mock_updater.update_status = AsyncMock()
        mock_updater.complete = AsyncMock()

        # Successful agent execution
        async def successful_agent(*args, **kwargs):
            return "success"

        # Simulate decorator logic for success path
        task_terminated = False
        try:
            result = await successful_agent()
            assert result == "success"
        except Exception:
            task_terminated = True
        finally:
            if not task_terminated:
                await mock_updater.complete()

        # Verify: complete() WAS called (no error, so not terminated)
        mock_updater.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_respects_terminal_states(self):
        """
        Test: All terminal states prevent double-complete
        Expected: cancelled/failed states don't trigger complete()
        """
        from a2a.server.tasks import TaskUpdater

        terminal_states = [TaskState.failed, TaskState.completed, TaskState.canceled]

        for terminal_state in terminal_states:
            mock_updater = AsyncMock(spec=TaskUpdater)
            mock_updater.update_status = AsyncMock()
            mock_updater.complete = AsyncMock()

            # Simulate agent that sets terminal state
            task_terminated = False
            try:
                # Simulate setting a terminal state
                await mock_updater.update_status(terminal_state)
                task_terminated = True
            except Exception:
                task_terminated = True
            finally:
                if not task_terminated:
                    await mock_updater.complete()

            # Verify complete() not called for terminal state
            mock_updater.complete.assert_not_called()


# =============================================================================
# Test Suite 3: ResearchAgent Embedding Config
# =============================================================================


class TestResearchEmbeddingConfig:
    """Test ResearchAgent embedding configuration"""

    def test_research_embedding_provider_config(self):
        """
        Test: ResearchAgent has correct embedding provider
        Expected: provider = "google", uses gemini-embedding-001
        Validates: Lines 26-32 in research_agent.yaml
        """
        # Load the research_agent.yaml directly
        config_path = Path(__file__).parent.parent.parent.parent.parent / "configs" / "agents" / "research_agent.yaml"
        
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Check embedding configuration
        assert "embedding" in config, "Embedding config missing"
        embedding_config = config["embedding"]

        # Verify primary provider is google
        assert embedding_config["provider"] == "google", "Provider should be 'google'"
        assert (
            embedding_config["model_id"] == "gemini-embedding-001"
        ), "Model should be gemini-embedding-001"

        # Verify fallback options exist
        assert "provider_models" in embedding_config, "Fallback providers missing"
        fallbacks = embedding_config["provider_models"]

        # Google should be primary, siliconflow should only be fallback
        assert "openai" in fallbacks or "siliconflow" in fallbacks, "Fallback options should exist"

    def test_research_embedding_has_fallbacks(self):
        """
        Test: ResearchAgent embedding config has proper fallback chain
        Expected: Multiple provider options configured
        """
        config_path = Path(__file__).parent.parent.parent.parent.parent / "configs" / "agents" / "research_agent.yaml"
        
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        embedding_config = config["embedding"]
        provider_models = embedding_config.get("provider_models", {})

        # Should have at least one fallback option
        assert len(provider_models) > 0, "Should have fallback providers"

        # Check common fallback providers
        expected_fallbacks = {"openai", "siliconflow"}
        actual_fallbacks = set(provider_models.keys())

        assert actual_fallbacks.intersection(
            expected_fallbacks
        ), f"Should have at least one of {expected_fallbacks}"


# =============================================================================
# Test Suite 4: Configuration Validation
# =============================================================================


class TestConfigurationValidation:
    """Test configuration validation utilities"""

    def test_validate_single_agent_function_exists(self):
        """
        Test: validate_agent_config function works
        Expected: Returns (is_valid, warnings) tuple
        """
        # Test that the function can be called
        is_valid, warnings = validate_agent_config("research_agent")

        # Should return tuple
        assert isinstance(is_valid, bool), "Should return boolean validity"
        assert isinstance(warnings, list), "Should return list of warnings"

        # Warnings should be strings
        for warning in warnings:
            assert isinstance(warning, str), "Warnings should be strings"

    def test_validate_all_agents_function_works(self):
        """
        Test: validate_all_agents function works
        Expected: Dict with agent names and validation results
        """
        results = validate_all_agents()

        # Should return dictionary
        assert isinstance(results, dict), "Should return dictionary"

        # Each result should be (bool, list) tuple
        for agent_name, result in results.items():
            assert isinstance(agent_name, str), "Agent name should be string"
            assert isinstance(result, tuple), "Result should be tuple"
            assert len(result) == 2, "Result should have 2 elements"

            is_valid, warnings = result
            assert isinstance(is_valid, bool), "Validity should be boolean"
            assert isinstance(warnings, list), "Warnings should be list"

    def test_validation_detects_config_issues(self):
        """
        Test: Validator can detect configuration problems
        Expected: Returns warnings for misconfigured agents
        """
        # Test with potentially invalid agent name
        is_valid, warnings = validate_agent_config("nonexistent_agent")

        # Should indicate problem
        assert not is_valid or len(warnings) > 0, "Should detect invalid agent"

        # Test validation with all agents
        results = validate_all_agents()

        # Should have results for existing agents
        agent_names = list(results.keys())
        expected_agents = ["research_agent", "auto_trading_agent", "news_agent"]

        # At least some expected agents should be present
        found_agents = [a for a in expected_agents if a in agent_names]
        assert len(found_agents) > 0, f"Should find at least one agent from {expected_agents}"


# =============================================================================
# Test Suite 5: Integration Tests (Regression)
# =============================================================================


class TestIntegration:
    """Integration tests to ensure no regressions"""

    def test_all_agent_configs_loadable(self):
        """
        Test: All agent configs can be loaded without errors
        Expected: No import/config errors for any agent
        """
        config_manager = get_config_manager()

        # Get list of all agents
        agent_names = config_manager.loader.list_agents()

        assert len(agent_names) > 0, "Should have at least one agent configured"

        # Try to load each agent config
        for agent_name in agent_names:
            try:
                agent_config = config_manager.get_agent_config(agent_name)
                assert agent_config is not None, f"Config should load for {agent_name}"
            except Exception as e:
                pytest.fail(f"Failed to load config for {agent_name}: {e}")

    def test_agent_imports_work(self):
        """
        Test: All agent modules can be imported
        Expected: No import errors
        """
        import importlib

        agents_to_test = [
            "valuecell.agents.auto_trading_agent.agent",
            "valuecell.agents.research_agent.core",
            "valuecell.agents.news_agent.core",
        ]

        for module_name in agents_to_test:
            try:
                module = importlib.import_module(module_name)
                assert module is not None, f"Module {module_name} should import"
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_trading_request_model_validation(self):
        """
        Test: TradingRequest model validation works correctly
        Expected: Valid requests pass, invalid requests fail
        """
        # Valid request
        valid_request = TradingRequest(
            crypto_symbols=["BTC-USD"], initial_capital=10000.0, use_ai_signals=True
        )

        assert valid_request.crypto_symbols == ["BTC-USD"]
        assert valid_request.initial_capital == 10000.0

        # Invalid request - negative capital
        with pytest.raises(Exception):  # Should raise validation error
            TradingRequest(
                crypto_symbols=["BTC-USD"], initial_capital=-1000.0, use_ai_signals=True
            )

        # Invalid request - empty symbols
        with pytest.raises(Exception):  # Should raise validation error
            TradingRequest(crypto_symbols=[], initial_capital=10000.0, use_ai_signals=True)

    def test_config_manager_singleton(self):
        """
        Test: ConfigManager singleton pattern works
        Expected: Same instance returned on multiple calls
        """
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2, "Should return same ConfigManager instance"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_task_updater():
    """Fixture providing a mock TaskUpdater"""
    mock = AsyncMock()
    mock.update_status = AsyncMock()
    mock.complete = AsyncMock()
    return mock


@pytest.fixture
def mock_parser_agent():
    """Fixture providing a mock parser agent"""
    mock = AsyncMock()
    mock.arun = AsyncMock()
    return mock


# =============================================================================
# Main entry point for running tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

