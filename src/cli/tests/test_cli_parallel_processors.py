"""Tests for parallel worker processing with processor architecture."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestParallelWorkerProcessorPath:
    """Test that parallel workers use processor architecture correctly."""

    @pytest.fixture
    def v2_test_files(self, tmp_path: Path) -> list[Path]:
        """Create multiple v2.0 test files."""
        # Load base test vector
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            data = json.load(f)

        # Ensure v2.0 version
        data["version"] = "2.0"

        # Create 3 test files
        test_files = []
        for i in range(3):
            test_file = tmp_path / f"v2_test_{i}.json"
            with open(test_file, "w") as f:
                json.dump(data, f)
            test_files.append(test_file)

        return test_files

    @pytest.fixture
    def v3_test_files(self, tmp_path: Path) -> list[Path]:
        """Create multiple v3.0 test files."""
        # Load v3 test vector
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            data = json.load(f)

        # Create 3 test files
        test_files = []
        for i in range(3):
            test_file = tmp_path / f"v3_test_{i}.json"
            with open(test_file, "w") as f:
                json.dump(data, f)
            test_files.append(test_file)

        return test_files

    @pytest.fixture
    def output_dir(self, tmp_path: Path) -> Path:
        """Create output directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        return output_dir

    def test_worker_processes_v2_with_processors_disabled(
        self, v2_test_files, output_dir, monkeypatch
    ):
        """Test worker processes v2 files with processors disabled (legacy path)."""
        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_single_file_worker

        # Ensure processors disabled
        monkeypatch.setattr(config_module.config, "use_version_processors", False)

        test_file = v2_test_files[0]
        output_file = output_dir / f"{test_file.stem}.json"

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            result, error = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=1,
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should succeed
        assert result is not None
        assert error is None
        assert result[0] == test_file

    def test_worker_processes_v2_with_processors_enabled(
        self, v2_test_files, output_dir, monkeypatch
    ):
        """Test worker processes v2 files with processors enabled (processor path)."""
        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_single_file_worker

        # Enable processors
        monkeypatch.setattr(config_module.config, "use_version_processors", True)

        test_file = v2_test_files[0]
        output_file = output_dir / f"{test_file.stem}.json"

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            result, error = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=2,  # Test with non-default value
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should succeed
        assert result is not None
        assert error is None
        assert result[0] == test_file

    def test_worker_processes_v3_with_processors_enabled(
        self, v3_test_files, output_dir, monkeypatch
    ):
        """Test worker processes v3 files with processors enabled."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_single_file_worker

        # Reload config with v3 enabled
        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        # Enable processors
        monkeypatch.setattr(new_config, "use_version_processors", True)

        test_file = v3_test_files[0]
        output_file = output_dir / f"{test_file.stem}.json"

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            result, error = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=1,
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should succeed
        assert result is not None
        assert error is None
        assert result[0] == test_file

    def test_worker_v3_with_v2_params_shows_warning(
        self, v3_test_files, output_dir, monkeypatch, capsys
    ):
        """Test worker shows warning when v2 params used with v3 input."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_single_file_worker

        # Reload config with v3 enabled
        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        # Enable processors
        monkeypatch.setattr(new_config, "use_version_processors", True)

        test_file = v3_test_files[0]
        output_file = output_dir / f"{test_file.stem}.json"

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            result, error = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=2,  # V2 parameter
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should succeed but with warning
        assert result is not None
        assert error is None

        # Check for warning in stderr
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "v3.0" in captured.err
        assert test_file.name in captured.err

    def test_batch_processes_v2_with_processors(self, v2_test_files, output_dir, monkeypatch):
        """Test batch processing of v2 files with processors enabled."""
        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_file_batch

        # Enable processors
        monkeypatch.setattr(config_module.config, "use_version_processors", True)

        # Create file batch
        file_batch = [(f, output_dir / f"{f.stem}.json") for f in v2_test_files]

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            results, errors = process_file_batch(
                file_batch=file_batch,
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=1,
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should process all files successfully
        assert len(results) == 3
        assert len(errors) == 0
        assert all(r[0] in v2_test_files for r in results)

    def test_batch_processes_v3_with_processors(
        self, v3_test_files, output_dir, monkeypatch
    ):
        """Test batch processing of v3 files with processors enabled."""
        # Enable v3 format
        monkeypatch.setenv("FUZZER_BRIDGE_V3", "true")

        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_file_batch

        # Reload config with v3 enabled
        new_config = config_module.FuzzerBridgeConfig.from_env()
        monkeypatch.setattr(config_module, "config", new_config)

        # Enable processors
        monkeypatch.setattr(new_config, "use_version_processors", True)

        # Create file batch
        file_batch = [(f, output_dir / f"{f.stem}.json") for f in v3_test_files]

        # Mock the builder to avoid t8n execution
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}):
            results, errors = process_file_batch(
                file_batch=file_batch,
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
                num_blocks=1,
                block_strategy="distribute",
                block_time=12,
                random_blocks=False,
            )

        # Should process all files successfully
        assert len(results) == 3
        assert len(errors) == 0
        assert all(r[0] in v3_test_files for r in results)

    def test_feature_flag_controls_routing(self, v2_test_files, output_dir, monkeypatch):
        """Test that feature flag properly controls processor routing."""
        from ..fuzzer_bridge import config as config_module
        from ..fuzzer_bridge.cli import process_single_file_worker

        test_file = v2_test_files[0]
        output_file = output_dir / f"{test_file.stem}.json"

        # Mock the builder to track which methods are called
        from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder

        with patch.object(
            BlocktestBuilder, "build_blocktest", return_value={"test": "fixture"}
        ) as mock_build:
            # Test with processors disabled
            monkeypatch.setattr(config_module.config, "use_version_processors", False)

            result1, error1 = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
            )

            # Should succeed
            assert result1 is not None
            assert error1 is None
            assert mock_build.called

            # Reset mock
            mock_build.reset_mock()

            # Test with processors enabled
            monkeypatch.setattr(config_module.config, "use_version_processors", True)

            result2, error2 = process_single_file_worker(
                file_info=(test_file, output_file),
                fork=None,
                pretty=False,
                merge=False,
                evm_bin=None,
            )

            # Should succeed
            assert result2 is not None
            assert error2 is None
            assert mock_build.called

            # Both paths should produce valid results
            assert result1[1] == result2[1]  # Same fixture structure
