"""End-to-end integration tests for processor architecture."""

import json
from pathlib import Path

import pytest

from ethereum_test_forks import Prague

from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
from ..fuzzer_bridge.config import config


class TestProcessorIntegrationE2E:
    """End-to-end integration tests."""

    @pytest.fixture
    def v2_test_data(self) -> dict:
        """Load v2.0 test vector."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            return json.load(f)

    @pytest.fixture
    def v3_test_data(self) -> dict:
        """Load v3.0 test vector."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled")

        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            return json.load(f)

    def test_v2_with_legacy_path(self, v2_test_data):
        """Test V2 processing with legacy path (processors disabled)."""
        # Ensure processors disabled (default)
        if config.use_version_processors:
            pytest.skip("Processors enabled, testing legacy path")

        builder = BlocktestBuilder()
        result = builder.build_blocktest(v2_test_data, num_blocks=2)

        # Should produce valid fixture
        assert result is not None
        assert isinstance(result, dict)

    def test_v3_with_legacy_path(self, v3_test_data):
        """Test V3 processing with legacy path (processors disabled)."""
        if config.use_version_processors:
            pytest.skip("Processors enabled, testing legacy path")

        builder = BlocktestBuilder()
        result = builder.build_blocktest(v3_test_data)

        # Should produce valid fixture
        assert result is not None
        assert isinstance(result, dict)


class TestProcessorPathEnabled:
    """Tests with processor path enabled."""

    @pytest.fixture
    def v2_test_data(self) -> dict:
        """Load v2.0 test vector."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            return json.load(f)

    @pytest.fixture
    def v3_test_data(self) -> dict:
        """Load v3.0 test vector."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled")

        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            return json.load(f)

    def test_v2_with_processor_path(self, v2_test_data, monkeypatch):
        """Test V2 processing with processor path enabled."""
        # Enable processors for this test
        monkeypatch.setenv("FUZZER_USE_PROCESSORS", "true")

        # Need to reload config after setting env var
        from ..fuzzer_bridge import config as config_module

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()
        result = builder.build_blocktest(v2_test_data, num_blocks=2)

        # Should produce valid fixture
        assert result is not None
        assert isinstance(result, dict)

    def test_v3_with_processor_path(self, v3_test_data, monkeypatch):
        """Test V3 processing with processor path enabled."""
        # Enable both v3 and processors
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")
        monkeypatch.setenv("FUZZER_USE_PROCESSORS", "true")

        # Reload config
        from ..fuzzer_bridge import config as config_module

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()
        result = builder.build_blocktest(v3_test_data)

        # Should produce valid fixture
        assert result is not None
        assert isinstance(result, dict)
