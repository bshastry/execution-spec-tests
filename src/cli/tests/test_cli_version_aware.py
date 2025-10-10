"""Tests for CLI version-aware processing with early detection."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ..fuzzer_bridge.cli import process_single_file


class TestCLIVersionDetection:
    """Test early version detection in CLI."""

    @pytest.fixture
    def v2_test_file(self, tmp_path: Path) -> Path:
        """Create v2.0 test file."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            data = json.load(f)

        # Ensure v2.0 version
        data["version"] = "2.0"

        test_file = tmp_path / "v2_test.json"
        with open(test_file, "w") as f:
            json.dump(data, f)

        return test_file

    @pytest.fixture
    def v3_test_file(self, tmp_path: Path) -> Path:
        """Create v3.0 test file."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            data = json.load(f)

        test_file = tmp_path / "v3_test.json"
        with open(test_file, "w") as f:
            json.dump(data, f)

        return test_file

    @pytest.fixture
    def output_path(self, tmp_path: Path) -> Path:
        """Create output directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        return output_dir

    def test_version_detection_disabled_by_default(self, v2_test_file, output_path, capsys):
        """Test that version detection is disabled when processors disabled."""
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
        from ..fuzzer_bridge.config import config

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Process file with processors disabled (default)
            with patch.object(config, "use_version_processors", False):
                process_single_file(
                    input_file=v2_test_file,
                    output_path=output_path,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    quiet=False,
                )

        # Should NOT show version detection message
        captured = capsys.readouterr()
        assert "Detected version:" not in captured.err

    def test_version_detection_when_enabled(self, v2_test_file, output_path, capsys):
        """Test that version is detected early when processors enabled."""
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
        from ..fuzzer_bridge.config import config

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors
            with patch.object(config, "use_version_processors", True):
                process_single_file(
                    input_file=v2_test_file,
                    output_path=output_path,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    quiet=False,
                )

        # Should show version detection message
        captured = capsys.readouterr()
        assert "Detected version: 2.0" in captured.err

    def test_v3_version_detection(self, v3_test_file, output_path, capsys, monkeypatch):
        """Test v3.0 version detection."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors
            with patch.object(new_config, "use_version_processors", True):
                # Need to patch the config module's config to use new_config
                with patch.object(config_module, "config", new_config):
                    process_single_file(
                        input_file=v3_test_file,
                        output_path=output_path,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        quiet=False,
                    )

        # Should show version detection message
        captured = capsys.readouterr()
        assert "Detected version: 3.0" in captured.err

    def test_quiet_mode_suppresses_version_message(self, v2_test_file, output_path, capsys):
        """Test that quiet mode suppresses version detection message."""
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
        from ..fuzzer_bridge.config import config

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors but use quiet mode
            with patch.object(config, "use_version_processors", True):
                process_single_file(
                    input_file=v2_test_file,
                    output_path=output_path,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    quiet=True,  # Quiet mode
                )

        # Should NOT show version detection message
        captured = capsys.readouterr()
        assert "Detected version:" not in captured.err


class TestCLIV2ParamsWithV3Warning:
    """Test warnings when v2 params are used with v3 input."""

    @pytest.fixture
    def v3_test_file(self, tmp_path: Path) -> Path:
        """Create v3.0 test file."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            data = json.load(f)

        test_file = tmp_path / "v3_test.json"
        with open(test_file, "w") as f:
            json.dump(data, f)

        return test_file

    @pytest.fixture
    def output_path(self, tmp_path: Path) -> Path:
        """Create output directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        return output_dir

    def test_warning_when_num_blocks_with_v3(
        self, v3_test_file, output_path, capsys, monkeypatch
    ):
        """Test warning when num_blocks parameter used with v3.0."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors and use v2 param with v3 input
            with patch.object(new_config, "use_version_processors", True):
                with patch.object(config_module, "config", new_config):
                    process_single_file(
                        input_file=v3_test_file,
                        output_path=output_path,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        quiet=False,
                        num_blocks=2,  # V2 parameter
                    )

        # Should show warning
        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "v3.0" in captured.err
        assert "ignores" in captured.err.lower()

    def test_warning_when_block_strategy_with_v3(
        self, v3_test_file, output_path, capsys, monkeypatch
    ):
        """Test warning when block_strategy parameter used with v3.0."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors and use v2 param with v3 input
            with patch.object(new_config, "use_version_processors", True):
                with patch.object(config_module, "config", new_config):
                    process_single_file(
                        input_file=v3_test_file,
                        output_path=output_path,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        quiet=False,
                        block_strategy="first-block",  # V2 parameter
                    )

        # Should show warning
        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "v3.0" in captured.err

    def test_warning_when_random_blocks_with_v3(
        self, v3_test_file, output_path, capsys, monkeypatch
    ):
        """Test warning when random_blocks parameter used with v3.0."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors and use v2 param with v3 input
            with patch.object(new_config, "use_version_processors", True):
                with patch.object(config_module, "config", new_config):
                    process_single_file(
                        input_file=v3_test_file,
                        output_path=output_path,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        quiet=False,
                        random_blocks=True,  # V2 parameter
                    )

        # Should show warning
        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "v3.0" in captured.err

    def test_no_warning_with_v2_input(self, tmp_path, output_path, capsys):
        """Test no warning when v2 params used with v2 input."""
        # Create v2 test file
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            data = json.load(f)
        data["version"] = "2.0"

        test_file = tmp_path / "v2_test.json"
        with open(test_file, "w") as f:
            json.dump(data, f)

        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
        from ..fuzzer_bridge.config import config

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors and use v2 params with v2 input
            with patch.object(config, "use_version_processors", True):
                process_single_file(
                    input_file=test_file,
                    output_path=output_path,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    quiet=False,
                    num_blocks=2,
                    block_strategy="distribute",
                )

        # Should NOT show warning (v2 params valid for v2 input)
        captured = capsys.readouterr()
        # If there's a warning, it shouldn't be about ignoring parameters
        if "Warning:" in captured.err:
            assert "ignores" not in captured.err.lower()

    def test_quiet_mode_suppresses_warnings(self, v3_test_file, output_path, capsys, monkeypatch):
        """Test that quiet mode suppresses parameter mismatch warnings."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        builder = BlocktestBuilder()

        # Mock the build_blocktest to avoid t8n execution
        with patch.object(builder, "build_blocktest", return_value={"test": "fixture"}):
            # Enable processors, use v2 param with v3 input, but quiet mode
            with patch.object(new_config, "use_version_processors", True):
                with patch.object(config_module, "config", new_config):
                    process_single_file(
                        input_file=v3_test_file,
                        output_path=output_path,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        quiet=True,  # Quiet mode
                        num_blocks=2,  # V2 parameter
                    )

        # Should NOT show warning in quiet mode
        captured = capsys.readouterr()
        assert "Warning:" not in captured.err
