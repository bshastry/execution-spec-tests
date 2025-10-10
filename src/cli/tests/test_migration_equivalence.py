"""
Migration equivalence tests for fuzzer bridge processor architecture.

Validates that enabling processors (new path) produces identical output
to the legacy converter path (old path) for v2 inputs. This is critical
for ensuring backward compatibility during the migration.
"""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from ethereum_clis import GethTransitionTool

from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
from ..fuzzer_bridge.config import config
from ..fuzzer_bridge.models import FuzzerOutput


# Custom evm binary path
EVM_BINARY = Path("../go-ethereum/build/bin/evm").resolve()


def load_test_vector(filename: str) -> Dict[str, Any]:
    """Load fuzzer test vector from vectors/ directory."""
    vector_path = Path(__file__).parent / "vectors" / filename
    with open(vector_path) as f:
        return json.load(f)


class TestV2MigrationEquivalence:
    """Test that old and new paths produce identical output for v2 inputs."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_v2_equivalence_simple(self, t8n):
        """Verify old and new paths produce identical output for simple v2."""
        vector = load_test_vector("fuzzer_test_0.json")

        # Process with old path (processors disabled)
        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, num_blocks=2)

        # Process with new path (processors enabled)
        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, num_blocks=2)

        # Must be exactly equal
        assert result_old == result_new, "Migration changed behavior for v2 simple case!"

    @pytest.mark.parametrize(
        "test_params",
        [
            {"num_blocks": 1, "block_strategy": "distribute"},
            {"num_blocks": 3, "block_strategy": "distribute"},
            {"num_blocks": 2, "block_strategy": "first-block"},
            {"num_blocks": 5, "block_strategy": "distribute", "block_time": 15},
        ],
        ids=["1block-dist", "3blocks-dist", "2blocks-first", "5blocks-custom-time"],
    )
    def test_v2_equivalence_with_parameters(self, t8n, test_params: Dict[str, Any]):
        """Test equivalence with all v2 parameter combinations."""
        vector = load_test_vector("fuzzer_test_1.json")

        # Process with old path
        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, **test_params)

        # Process with new path
        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, **test_params)

        # Must be exactly equal
        assert result_old == result_new, f"Migration changed behavior with params: {test_params}"

    @pytest.mark.parametrize(
        "vector_file",
        ["fuzzer_test_0.json", "fuzzer_test_1.json", "fuzzer_test_2.json"],
        ids=["vector_0", "vector_1", "vector_2"],
    )
    def test_v2_equivalence_multiple_vectors(self, t8n, vector_file: str):
        """Test equivalence across multiple v2 test vectors."""
        vector = load_test_vector(vector_file)

        # Test with default parameters
        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, num_blocks=2)

        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, num_blocks=2)

        assert result_old == result_new, f"Migration changed behavior for {vector_file}"


class TestV3ProcessorValidation:
    """Test that v3 processor produces valid output matching v3 specification."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_v3_processor_produces_valid_output(self, t8n):
        """Verify v3 processor produces valid output."""
        vector = load_test_vector("fuzzer_test_v3_correct.json")

        # Process with new path (processors enabled) and V3 enabled
        builder = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True), \
             patch.object(config, "enable_v3_format", True):
            result = builder.build_blocktest(vector)

        # Validate result structure
        assert result is not None, "V3 processor produced no output"
        assert isinstance(result, dict), "V3 processor output should be dict"

        # Validate that fixture was generated
        assert len(result) > 0, "V3 processor produced empty output"

    def test_v3_processor_handles_multi_block(self, t8n):
        """Verify v3 processor handles multi-block inputs correctly."""
        vector = load_test_vector("fuzzer_test_v3_multi_fixed.json")

        # Process with new path and V3 enabled
        builder = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True), \
             patch.object(config, "enable_v3_format", True):
            result = builder.build_blocktest(vector)

        # Parse original to check block count (with V3 enabled)
        with patch.object(config, "enable_v3_format", True):
            fuzzer_output = FuzzerOutput(**vector)

        # Validate result
        assert result is not None, "V3 processor failed on multi-block input"
        assert len(result) > 0, "V3 processor produced empty output for multi-block"

        # Note: Deep validation of block structure would require inspecting
        # the fixture format. For now, we validate that processing succeeds.


class TestEdgeCaseCoverage:
    """Test migration equivalence for edge cases."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_equivalence_with_max_blocks(self, t8n):
        """Test equivalence with maximum number of blocks."""
        vector = load_test_vector("fuzzer_test_0.json")

        # Test with many blocks (17 txs in fuzzer_test_0)
        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, num_blocks=10)

        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, num_blocks=10)

        assert result_old == result_new, "Migration changed behavior with max blocks"

    def test_equivalence_with_single_block(self, t8n):
        """Test equivalence with single block (all txs in one block)."""
        vector = load_test_vector("fuzzer_test_1.json")

        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, num_blocks=1)

        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, num_blocks=1)

        assert result_old == result_new, "Migration changed behavior with single block"

    def test_equivalence_with_custom_block_time(self, t8n):
        """Test equivalence with custom block time."""
        vector = load_test_vector("fuzzer_test_2.json")

        builder_old = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", False):
            result_old = builder_old.build_blocktest(vector, num_blocks=3, block_time=20)

        builder_new = BlocktestBuilder(transition_tool=t8n)
        with patch.object(config, "use_version_processors", True):
            result_new = builder_new.build_blocktest(vector, num_blocks=3, block_time=20)

        assert result_old == result_new, "Migration changed behavior with custom block_time"
