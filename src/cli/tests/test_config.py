"""Tests for fuzzer bridge configuration."""

import pytest

from ..fuzzer_bridge.config import FuzzerBridgeConfig


class TestFuzzerBridgeConfig:
    """Test fuzzer bridge configuration."""

    def test_config_has_use_version_processors_flag(self):
        """Test that config has use_version_processors flag."""
        config = FuzzerBridgeConfig()
        assert hasattr(config, "use_version_processors")

    def test_use_version_processors_defaults_to_false(self):
        """Test that use_version_processors defaults to False."""
        config = FuzzerBridgeConfig()
        assert config.use_version_processors is False

    def test_use_version_processors_loads_from_env(self, monkeypatch):
        """Test that use_version_processors can be enabled via env var."""
        monkeypatch.setenv("FUZZER_USE_PROCESSORS", "true")
        config = FuzzerBridgeConfig.from_env()
        assert config.use_version_processors is True

    def test_use_version_processors_env_var_case_insensitive(self, monkeypatch):
        """Test that env var is case insensitive."""
        monkeypatch.setenv("FUZZER_USE_PROCESSORS", "TRUE")
        config = FuzzerBridgeConfig.from_env()
        assert config.use_version_processors is True

    def test_use_version_processors_false_when_env_not_true(self, monkeypatch):
        """Test that flag is False when env var is not 'true'."""
        monkeypatch.setenv("FUZZER_USE_PROCESSORS", "false")
        config = FuzzerBridgeConfig.from_env()
        assert config.use_version_processors is False
