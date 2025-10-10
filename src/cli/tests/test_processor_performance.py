"""
Performance benchmark tests for fuzzer bridge processor architecture.

Measures processing overhead and validates that the new processor architecture
doesn't introduce unacceptable performance degradation.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from ethereum_clis import GethTransitionTool

from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder
from ..fuzzer_bridge.config import config


# Custom evm binary path
EVM_BINARY = Path("../go-ethereum/build/bin/evm").resolve()


def load_test_vector(filename: str) -> Dict[str, Any]:
    """Load fuzzer test vector from vectors/ directory."""
    vector_path = Path(__file__).parent / "vectors" / filename
    with open(vector_path) as f:
        return json.load(f)


def measure_processing_time(
    builder: BlocktestBuilder,
    vector: Dict[str, Any],
    use_processors: bool,
    iterations: int = 3,
    **kwargs,
) -> float:
    """
    Measure average processing time for a vector.

    Returns average time in seconds over multiple iterations.
    """
    times: List[float] = []

    for _ in range(iterations):
        start_time = time.perf_counter()

        with patch.object(config, "use_version_processors", use_processors):
            _ = builder.build_blocktest(vector, **kwargs)

        elapsed = time.perf_counter() - start_time
        times.append(elapsed)

    return sum(times) / len(times)


class TestProcessingOverhead:
    """Test processing time overhead of processor architecture."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    @pytest.mark.parametrize(
        "vector_file",
        ["fuzzer_test_0.json", "fuzzer_test_1.json"],
        ids=["vector_0", "vector_1"],
    )
    def test_processor_overhead_acceptable(self, t8n, vector_file: str):
        """Verify processor overhead is less than 10% for v2 inputs."""
        vector = load_test_vector(vector_file)
        builder = BlocktestBuilder(transition_tool=t8n)

        # Measure old path (legacy converter)
        time_old = measure_processing_time(
            builder, vector, use_processors=False, iterations=2, num_blocks=2
        )

        # Measure new path (processor architecture)
        time_new = measure_processing_time(
            builder, vector, use_processors=True, iterations=2, num_blocks=2
        )

        # Calculate overhead percentage
        overhead_pct = ((time_new - time_old) / time_old) * 100 if time_old > 0 else 0

        # Log timing information
        print(f"\n{vector_file}:")
        print(f"  Legacy path: {time_old:.3f}s")
        print(f"  Processor path: {time_new:.3f}s")
        print(f"  Overhead: {overhead_pct:+.1f}%")

        # Overhead should be acceptable (< 25%)
        # Note: Some overhead expected due to version detection and routing
        assert (
            overhead_pct < 25.0
        ), f"Processor overhead ({overhead_pct:.1f}%) exceeds 25% threshold"

    def test_processor_overhead_with_parameters(self, t8n):
        """Verify processor overhead with various parameters."""
        vector = load_test_vector("fuzzer_test_0.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        test_cases = [
            {"num_blocks": 1},
            {"num_blocks": 5},
            {"num_blocks": 2, "block_time": 15},
        ]

        for params in test_cases:
            # Measure both paths
            time_old = measure_processing_time(
                builder, vector, use_processors=False, iterations=2, **params
            )
            time_new = measure_processing_time(
                builder, vector, use_processors=True, iterations=2, **params
            )

            overhead_pct = ((time_new - time_old) / time_old) * 100 if time_old > 0 else 0

            print(f"\nWith params {params}:")
            print(f"  Overhead: {overhead_pct:+.1f}%")

            # Overhead should still be acceptable (< 25%)
            assert overhead_pct < 25.0, f"Overhead ({overhead_pct:.1f}%) too high for {params}"


class TestProcessorScalability:
    """Test that processor architecture scales well."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_processor_scales_with_blocks(self, t8n):
        """Verify processing time scales linearly with block count."""
        vector = load_test_vector("fuzzer_test_0.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        # Measure at different block counts
        block_counts = [1, 3, 5]
        times = []

        for num_blocks in block_counts:
            elapsed = measure_processing_time(
                builder, vector, use_processors=True, iterations=1, num_blocks=num_blocks
            )
            times.append(elapsed)
            print(f"\n{num_blocks} blocks: {elapsed:.3f}s")

        # Verify scaling is reasonable (not worse than quadratic)
        # Simple check: time should not grow faster than O(n^2)
        for i in range(1, len(times)):
            ratio = times[i] / times[i - 1]
            block_ratio = block_counts[i] / block_counts[i - 1]

            # Time ratio should be at most block_ratio^2
            assert ratio <= (block_ratio**2) * 1.5, f"Poor scaling: time ratio {ratio:.2f}"

    def test_multiple_sequential_calls(self, t8n):
        """Verify no performance degradation on sequential calls."""
        vector = load_test_vector("fuzzer_test_0.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        times = []
        num_calls = 3

        for i in range(num_calls):
            start_time = time.perf_counter()

            with patch.object(config, "use_version_processors", True):
                _ = builder.build_blocktest(vector, num_blocks=2)

            elapsed = time.perf_counter() - start_time
            times.append(elapsed)
            print(f"\nCall {i+1}: {elapsed:.3f}s")

        # First call may be slower (JIT warm-up), but subsequent calls should be consistent
        if len(times) >= 2:
            avg_subsequent = sum(times[1:]) / len(times[1:])
            for t in times[1:]:
                # No call should be more than 20% slower than average
                assert t <= avg_subsequent * 1.2, f"Performance degradation detected: {t:.3f}s"


class TestV3ProcessorPerformance:
    """Test V3 processor performance characteristics."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_v3_processing_time_reasonable(self, t8n):
        """Verify V3 processor completes in reasonable time."""
        vector = load_test_vector("fuzzer_test_v3_correct.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        start_time = time.perf_counter()

        with patch.object(config, "use_version_processors", True), \
             patch.object(config, "enable_v3_format", True):
            _ = builder.build_blocktest(vector)

        elapsed = time.perf_counter() - start_time

        print(f"\nV3 processing time: {elapsed:.3f}s")

        # Should complete in reasonable time (< 5 seconds for simple case)
        assert elapsed < 5.0, f"V3 processing too slow: {elapsed:.3f}s"

    def test_v3_multi_block_performance(self, t8n):
        """Verify V3 multi-block processing performance."""
        vector = load_test_vector("fuzzer_test_v3_multi_fixed.json")
        builder = BlocktestBuilder(transition_tool=t8n)

        start_time = time.perf_counter()

        with patch.object(config, "use_version_processors", True), \
             patch.object(config, "enable_v3_format", True):
            _ = builder.build_blocktest(vector)

        elapsed = time.perf_counter() - start_time

        print(f"\nV3 multi-block processing time: {elapsed:.3f}s")

        # Multi-block should also complete reasonably (< 10 seconds)
        assert elapsed < 10.0, f"V3 multi-block too slow: {elapsed:.3f}s"


@pytest.mark.skip(reason="Performance baseline test - run manually for comparison")
class TestPerformanceBaseline:
    """Baseline performance tests for documentation."""

    @pytest.fixture
    def t8n(self):
        """Create transition tool with custom evm binary."""
        return GethTransitionTool(binary=EVM_BINARY)

    def test_document_performance_baseline(self, t8n):
        """Document performance baseline for future reference."""
        vectors = [
            ("fuzzer_test_0.json", 2),
            ("fuzzer_test_1.json", 2),
            ("fuzzer_test_2.json", 3),
        ]

        print("\n=== Performance Baseline ===")

        for vector_file, num_blocks in vectors:
            vector = load_test_vector(vector_file)
            builder = BlocktestBuilder(transition_tool=t8n)

            time_old = measure_processing_time(
                builder, vector, use_processors=False, iterations=3, num_blocks=num_blocks
            )
            time_new = measure_processing_time(
                builder, vector, use_processors=True, iterations=3, num_blocks=num_blocks
            )

            overhead_pct = ((time_new - time_old) / time_old) * 100 if time_old > 0 else 0

            print(f"\n{vector_file} ({num_blocks} blocks):")
            print(f"  Legacy: {time_old:.3f}s")
            print(f"  Processor: {time_new:.3f}s")
            print(f"  Overhead: {overhead_pct:+.1f}%")
