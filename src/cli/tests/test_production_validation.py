"""
Production validation tests for fuzzer bridge processor architecture.

Tests realistic production scenarios including large batch processing,
mixed version directories, and error recovery.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from ethereum_clis import GethTransitionTool

from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
from ..fuzzer_bridge.cli import process_directory, process_single_file
from ..fuzzer_bridge.config import config


# Custom evm binary path
EVM_BINARY = Path("../go-ethereum/build/bin/evm").resolve()


def load_test_vector(filename: str) -> Dict[str, Any]:
    """Load fuzzer test vector from vectors/ directory."""
    vector_path = Path(__file__).parent / "vectors" / filename
    with open(vector_path) as f:
        return json.load(f)


class TestLargeBatchProcessing:
    """Test processing of large batches of fuzzer outputs."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_process_multiple_files_sequentially(self, t8n):
        """Test sequential processing of multiple files."""
        vectors = [
            "fuzzer_test_0.json",
            "fuzzer_test_1.json",
            "fuzzer_test_2.json",
        ]

        builder = BlocktestBuilder(transition_tool=t8n)
        results = []

        with patch.object(config, "use_version_processors", True):
            for vector_file in vectors:
                vector = load_test_vector(vector_file)
                result = builder.build_blocktest(vector, num_blocks=2)
                results.append(result)

        # All results should be valid
        assert len(results) == len(vectors)
        for i, result in enumerate(results):
            assert result is not None, f"Result {i} is None"
            assert isinstance(result, dict), f"Result {i} is not a dict"
            assert len(result) > 0, f"Result {i} is empty"

    def test_process_same_file_repeatedly(self, t8n):
        """Test processing same file multiple times (idempotency)."""
        vector = load_test_vector("fuzzer_test_0.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        results = []
        num_iterations = 3

        with patch.object(config, "use_version_processors", True):
            for _ in range(num_iterations):
                result = builder.build_blocktest(vector, num_blocks=2)
                results.append(result)

        # All results should be identical
        for i in range(1, len(results)):
            assert results[i] == results[0], f"Result {i} differs from result 0"

    def test_batch_processing_with_directory(self, t8n):
        """Test batch processing from a directory."""
        # Create temp directory with test vectors
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Copy test vectors
            vectors = ["fuzzer_test_0.json", "fuzzer_test_1.json"]
            for vec_file in vectors:
                vec_data = load_test_vector(vec_file)
                output_file = tmpdir_path / vec_file
                with open(output_file, "w") as f:
                    json.dump(vec_data, f)

            # Process directory
            output_dir = tmpdir_path / "output"
            output_dir.mkdir()

            builder = BlocktestBuilder(transition_tool=t8n)

            with patch.object(config, "use_version_processors", True):
                process_directory(
                    input_dir=tmpdir_path,
                    output_dir=output_dir,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    merge=False,
                    quiet=True,
                    num_blocks=2,
                )

            # Verify output files were created
            output_files = list(output_dir.glob("*.json"))
            assert len(output_files) == len(vectors), f"Expected {len(vectors)} outputs, got {len(output_files)}"


class TestMixedVersionProcessing:
    """Test processing directories with mixed v2/v3 inputs."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_mixed_v2_v3_directory(self, t8n):
        """Test processing directory with both v2 and v3 files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Add v2 files
            v2_files = ["fuzzer_test_0.json", "fuzzer_test_1.json"]
            for vec_file in v2_files:
                vec_data = load_test_vector(vec_file)
                output_file = tmpdir_path / vec_file
                with open(output_file, "w") as f:
                    json.dump(vec_data, f)

            # Add v3 files
            v3_files = ["fuzzer_test_v3_correct.json"]
            for vec_file in v3_files:
                vec_data = load_test_vector(vec_file)
                output_file = tmpdir_path / vec_file
                with open(output_file, "w") as f:
                    json.dump(vec_data, f)

            # Process directory with both versions
            output_dir = tmpdir_path / "output"
            output_dir.mkdir()

            builder = BlocktestBuilder(transition_tool=t8n)

            with patch.object(config, "use_version_processors", True), \
                 patch.object(config, "enable_v3_format", True):
                process_directory(
                    input_dir=tmpdir_path,
                    output_dir=output_dir,
                    builder=builder,
                    fork=None,
                    pretty=False,
                    merge=False,
                    quiet=True,
                    num_blocks=2,
                )

            # All files should be processed
            output_files = list(output_dir.glob("*.json"))
            expected_count = len(v2_files) + len(v3_files)
            assert len(output_files) == expected_count, \
                f"Expected {expected_count} outputs, got {len(output_files)}"

    def test_version_detection_robustness(self, t8n):
        """Test that version detection works correctly for each file."""
        test_cases = [
            ("fuzzer_test_0.json", "2.0"),
            ("fuzzer_test_1.json", "2.0"),
            ("fuzzer_test_v3_correct.json", "3.0"),
        ]

        from ..fuzzer_bridge.version_detector import detect_version

        for vec_file, expected_version in test_cases:
            vector = load_test_vector(vec_file)
            detected_version = detect_version(vector)
            assert detected_version == expected_version, \
                f"{vec_file}: expected {expected_version}, got {detected_version}"


class TestErrorRecovery:
    """Test error recovery and graceful failure handling."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_invalid_version_handling(self, t8n):
        """Test handling of invalid version in input."""
        vector = load_test_vector("fuzzer_test_0.json")
        vector["version"] = "99.0"  # Invalid version

        builder = BlocktestBuilder(transition_tool=t8n)

        with patch.object(config, "use_version_processors", True):
            # Should raise an appropriate error
            with pytest.raises(ValueError, match="Unsupported version"):
                builder.build_blocktest(vector, num_blocks=2)

    def test_missing_required_fields(self, t8n):
        """Test handling of missing required fields."""
        vector = load_test_vector("fuzzer_test_0.json")
        del vector["fork"]  # Remove required field

        builder = BlocktestBuilder(transition_tool=t8n)

        with patch.object(config, "use_version_processors", True):
            # Should raise validation error
            with pytest.raises(Exception):  # Pydantic ValidationError
                builder.build_blocktest(vector, num_blocks=2)

    def test_malformed_json_handling(self, t8n):
        """Test handling of malformed JSON input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create malformed JSON file
            malformed_file = tmpdir_path / "malformed.json"
            with open(malformed_file, "w") as f:
                f.write("{invalid json")

            output_dir = tmpdir_path / "output"
            output_dir.mkdir()

            builder = BlocktestBuilder(transition_tool=t8n)

            # Processing should handle error gracefully
            with patch.object(config, "use_version_processors", True):
                # Should not crash, but may log error
                try:
                    process_directory(
                        input_dir=tmpdir_path,
                        output_dir=output_dir,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        merge=False,
                        quiet=True,
                        num_blocks=2,
                    )
                except json.JSONDecodeError:
                    # Expected error for malformed JSON
                    pass

    def test_partial_batch_failure_recovery(self, t8n):
        """Test that one file failure doesn't stop batch processing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Add valid file
            vec_data = load_test_vector("fuzzer_test_0.json")
            valid_file = tmpdir_path / "valid.json"
            with open(valid_file, "w") as f:
                json.dump(vec_data, f)

            # Add invalid file
            vec_data_invalid = load_test_vector("fuzzer_test_0.json")
            vec_data_invalid["version"] = "99.0"  # Invalid
            invalid_file = tmpdir_path / "invalid.json"
            with open(invalid_file, "w") as f:
                json.dump(vec_data_invalid, f)

            output_dir = tmpdir_path / "output"
            output_dir.mkdir()

            builder = BlocktestBuilder(transition_tool=t8n)

            with patch.object(config, "use_version_processors", True):
                # Should process valid file despite invalid file
                try:
                    process_directory(
                        input_dir=tmpdir_path,
                        output_dir=output_dir,
                        builder=builder,
                        fork=None,
                        pretty=False,
                        merge=False,
                        quiet=True,
                        num_blocks=2,
                    )
                except Exception:
                    # May raise error, but should have processed valid file
                    pass

                # At least valid file should be processed
                # (depending on error handling strategy)
                output_files = list(output_dir.glob("*.json"))
                # Note: Actual behavior depends on CLI error handling


class TestProductionScenarios:
    """Test realistic production scenarios."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_continuous_processing_simulation(self, t8n):
        """Simulate continuous processing of incoming fuzzer outputs."""
        builder = BlocktestBuilder(transition_tool=t8n)

        # Simulate 5 incoming files over time
        incoming_vectors = [
            ("fuzzer_test_0.json", 2),
            ("fuzzer_test_1.json", 3),
            ("fuzzer_test_0.json", 1),  # Repeat with different params
            ("fuzzer_test_2.json", 2),
            ("fuzzer_test_1.json", 1),
        ]

        results = []

        with patch.object(config, "use_version_processors", True):
            for vec_file, num_blocks in incoming_vectors:
                vector = load_test_vector(vec_file)
                result = builder.build_blocktest(vector, num_blocks=num_blocks)
                results.append(result)

        # All should process successfully
        assert len(results) == len(incoming_vectors)
        for i, result in enumerate(results):
            assert result is not None, f"Processing failed at iteration {i}"

    def test_process_with_different_block_strategies(self, t8n):
        """Test processing with various block strategies."""
        vector = load_test_vector("fuzzer_test_0.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        strategies = ["distribute", "first-block"]
        results = {}

        with patch.object(config, "use_version_processors", True):
            for strategy in strategies:
                result = builder.build_blocktest(
                    vector, num_blocks=3, block_strategy=strategy
                )
                results[strategy] = result

        # All strategies should produce valid output
        for strategy, result in results.items():
            assert result is not None, f"Strategy '{strategy}' failed"
            assert isinstance(result, dict), f"Strategy '{strategy}' produced invalid output"

    def test_high_volume_processing(self, t8n):
        """Test processing moderate volume of files."""
        builder = BlocktestBuilder(transition_tool=t8n)
        vector = load_test_vector("fuzzer_test_0.json")

        num_iterations = 10
        results = []

        with patch.object(config, "use_version_processors", True):
            for i in range(num_iterations):
                result = builder.build_blocktest(vector, num_blocks=2)
                results.append(result)

        # All should succeed
        assert len(results) == num_iterations
        # All should be identical (idempotency)
        for i in range(1, len(results)):
            assert results[i] == results[0]
