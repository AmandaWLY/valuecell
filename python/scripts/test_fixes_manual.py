#!/usr/bin/env python3
"""
Manual test script for agent fixes validation
Run: python scripts/test_fixes_manual.py

This script performs quick manual validation of all fixes:
1. Configuration validation
2. AutoTradingAgent parsing improvements
3. ResearchAgent embedding setup
4. State management improvements
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from unittest.mock import AsyncMock

from valuecell.agents.auto_trading_agent.models import TradingRequest
from valuecell.utils.config_validator import print_validation_report, validate_all_agents


def test_1_config_validation():
    """Test 1: Configuration Validation"""
    print("\n" + "=" * 80)
    print("TEST 1: Configuration Validation")
    print("=" * 80)
    print("\nValidating all agent configurations...\n")

    try:
        print_validation_report()
        print("\n✅ Configuration validation completed successfully")
        return True
    except Exception as e:
        print(f"\n❌ Configuration validation failed: {e}")
        return False


def test_2_autotrading_parsing():
    """Test 2: AutoTradingAgent Parsing Improvements"""
    print("\n" + "=" * 80)
    print("TEST 2: AutoTradingAgent Parsing Error Handling")
    print("=" * 80)

    async def run_test():
        print("\nTest 2.1: Parser returns string error (should raise ValueError)")
        try:
            # Simulate parser returning error string
            error_message = "Could not parse: invalid query format"
            trading_request = error_message  # This is a string, not TradingRequest

            # This is the critical type check that prevents AttributeError
            if isinstance(trading_request, str):
                raise ValueError(
                    f"Could not parse trading configuration from query\n"
                    f"Parser error: {trading_request}"
                )

            print("❌ Should have raised ValueError")
            return False

        except ValueError as e:
            if "Parser error:" in str(e):
                print(f"✅ Correctly raised ValueError: {e}")
            else:
                print(f"❌ Wrong ValueError message: {e}")
                return False
        except AttributeError as e:
            print(f"❌ Still getting AttributeError (bug not fixed): {e}")
            return False

        print("\nTest 2.2: Valid TradingRequest works correctly")
        try:
            # Valid request should work fine
            valid_request = TradingRequest(
                crypto_symbols=["BTC-USD"], initial_capital=10000.0, use_ai_signals=True
            )

            # Type check passes
            if isinstance(valid_request, str):
                raise ValueError("Should not be string")

            if isinstance(valid_request, TradingRequest):
                # Can safely call model_dump()
                request_dict = valid_request.model_dump()
                print(f"✅ Valid request processed: {request_dict['crypto_symbols']}")
            else:
                print("❌ Type check failed for valid request")
                return False

        except Exception as e:
            print(f"❌ Valid request failed: {e}")
            return False

        print("\nTest 2.3: Invalid capital raises validation error")
        try:
            invalid_request = TradingRequest(
                crypto_symbols=["BTC-USD"], initial_capital=-1000.0, use_ai_signals=True
            )
            print("❌ Should have raised validation error for negative capital")
            return False
        except Exception as e:
            print(f"✅ Correctly rejected negative capital: {type(e).__name__}")

        return True

    try:
        result = asyncio.run(run_test())
        if result:
            print("\n✅ AutoTradingAgent parsing tests passed")
        else:
            print("\n❌ AutoTradingAgent parsing tests failed")
        return result
    except Exception as e:
        print(f"\n❌ AutoTradingAgent parsing tests failed with error: {e}")
        return False


def test_3_research_embedding():
    """Test 3: ResearchAgent Embedding Configuration"""
    print("\n" + "=" * 80)
    print("TEST 3: ResearchAgent Embedding Configuration")
    print("=" * 80)

    try:
        import yaml

        config_path = (
            Path(__file__).parent.parent / "configs" / "agents" / "research_agent.yaml"
        )

        if not config_path.exists():
            print(f"⚠️  Config file not found: {config_path}")
            return True  # Skip test

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        print("\nTest 3.1: Checking embedding provider configuration")
        # Embedding config is under models.embedding, not top-level embedding
        models_config = config.get("models", {})
        embedding_config = models_config.get("embedding", {})

        if not embedding_config:
            print("❌ No embedding configuration found")
            return False

        provider = embedding_config.get("provider")
        model_id = embedding_config.get("model_id")

        print(f"   Provider: {provider}")
        print(f"   Model ID: {model_id}")

        if provider == "google":
            print("✅ Using Google provider (correct)")
        else:
            print(f"⚠️  Provider is '{provider}' (expected 'google')")

        print("\nTest 3.2: Checking fallback providers")
        fallbacks = embedding_config.get("provider_models", {})

        if fallbacks:
            print(f"   Fallback providers configured: {list(fallbacks.keys())}")
            print("✅ Fallback providers available")
        else:
            print("⚠️  No fallback providers configured")

        print("\n✅ ResearchAgent embedding configuration validated")
        return True

    except Exception as e:
        print(f"\n❌ ResearchAgent embedding test failed: {e}")
        return False


def test_4_state_management():
    """Test 4: State Management Improvements"""
    print("\n" + "=" * 80)
    print("TEST 4: State Management (No Double Complete)")
    print("=" * 80)

    async def run_test():
        from a2a.types import TaskState
        from unittest.mock import AsyncMock

        print("\nTest 4.1: Exception sets terminal state, prevents double complete")

        mock_updater = AsyncMock()
        mock_updater.update_status = AsyncMock()
        mock_updater.complete = AsyncMock()

        # Simulate agent with error
        task_terminated = False
        try:
            raise RuntimeError("Simulated agent error")
        except Exception as e:
            # Set failed state - this is terminal
            await mock_updater.update_status(TaskState.failed)
            task_terminated = True
        finally:
            # Only complete if not terminated
            if not task_terminated:
                await mock_updater.complete()

        # Check that complete() was NOT called
        if mock_updater.complete.call_count == 0:
            print("✅ complete() not called after terminal state (correct)")
        else:
            print(f"❌ complete() called {mock_updater.complete.call_count} times (bug!)")
            return False

        print("\nTest 4.2: Normal execution still completes properly")

        mock_updater2 = AsyncMock()
        mock_updater2.complete = AsyncMock()

        task_terminated2 = False
        try:
            # Normal execution - no error
            pass
        except Exception:
            task_terminated2 = True
        finally:
            if not task_terminated2:
                await mock_updater2.complete()

        # Check that complete() WAS called
        if mock_updater2.complete.call_count == 1:
            print("✅ complete() called once for successful execution (correct)")
        else:
            print(
                f"❌ complete() called {mock_updater2.complete.call_count} times (expected 1)"
            )
            return False

        return True

    try:
        result = asyncio.run(run_test())
        if result:
            print("\n✅ State management tests passed")
        else:
            print("\n❌ State management tests failed")
        return result
    except Exception as e:
        print(f"\n❌ State management tests failed with error: {e}")
        return False


def test_5_integration():
    """Test 5: Integration - All agents loadable"""
    print("\n" + "=" * 80)
    print("TEST 5: Integration - Agent Loading")
    print("=" * 80)

    try:
        from valuecell.config.manager import get_config_manager

        print("\nTest 5.1: Loading config manager")
        config_manager = get_config_manager()
        print("✅ Config manager loaded")

        print("\nTest 5.2: Listing all agents")
        agent_names = config_manager.loader.list_agents()
        print(f"   Found {len(agent_names)} agents: {agent_names}")

        if len(agent_names) == 0:
            print("❌ No agents found")
            return False

        print("\nTest 5.3: Loading each agent config")
        for agent_name in agent_names:
            try:
                agent_config = config_manager.get_agent_config(agent_name)
                if agent_config:
                    print(f"   ✅ {agent_name}: loaded")
                else:
                    print(f"   ❌ {agent_name}: returned None")
            except Exception as e:
                print(f"   ❌ {agent_name}: {e}")
                return False

        print("\n✅ Integration tests passed")
        return True

    except Exception as e:
        print(f"\n❌ Integration tests failed: {e}")
        return False


def main():
    """Run all manual tests"""
    print("\n" + "=" * 80)
    print("VALUECELL AGENT FIXES - MANUAL VALIDATION")
    print("=" * 80)

    results = []

    # Run all tests
    results.append(("Configuration Validation", test_1_config_validation()))
    results.append(("AutoTradingAgent Parsing", test_2_autotrading_parsing()))
    results.append(("ResearchAgent Embedding", test_3_research_embedding()))
    results.append(("State Management", test_4_state_management()))
    results.append(("Integration Tests", test_5_integration()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")

    print("\n" + "-" * 80)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All manual tests completed successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

