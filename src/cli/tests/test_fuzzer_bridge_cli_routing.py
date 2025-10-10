"""
CLI integration tests for fuzzer bridge version routing.

Tests that the converter automatically routes to v2.0 or v3.0
converters based on the version field in fuzzer output.
"""

import json
import warnings
from pathlib import Path

import pytest

from ethereum_test_forks import Prague

from ..fuzzer_bridge.config import config
from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer
from ..fuzzer_bridge.models import FuzzerOutput


class TestVersionRouting:
    """Test automatic version routing in blockchain_test_from_fuzzer."""

    @pytest.fixture
    def v2_fuzzer_output(self) -> FuzzerOutput:
        """Load v2.0 fuzzer output test vector."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            data = json.load(f)
        return FuzzerOutput(**data)

    @pytest.fixture
    def v3_fuzzer_output(self) -> FuzzerOutput:
        """Load v3.0 fuzzer output test vector."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled (set FUZZER_BRIDGE_V3=true)")

        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            data = json.load(f)
        return FuzzerOutput(**data)

    def test_routes_v2_correctly(self, v2_fuzzer_output: FuzzerOutput):
        """Test that v2.0 format routes to v2.0 converter."""
        assert v2_fuzzer_output.version == "2.0"

        # Call routing function
        blockchain_test = blockchain_test_from_fuzzer(
            v2_fuzzer_output,
            Prague,
            num_blocks=1,
            block_strategy="distribute",
            block_time=12,
        )

        # Verify it's a valid BlockchainTest
        assert blockchain_test is not None
        assert blockchain_test.pre is not None
        assert blockchain_test.blocks is not None
        assert len(blockchain_test.blocks) == 1

    def test_routes_v3_correctly(self, v3_fuzzer_output: FuzzerOutput):
        """Test that v3.0 format routes to v3.0 converter."""
        assert v3_fuzzer_output.version == "3.0"

        # Call routing function
        blockchain_test = blockchain_test_from_fuzzer(
            v3_fuzzer_output,
            Prague,
        )

        # Verify it's a valid BlockchainTest
        assert blockchain_test is not None
        assert blockchain_test.pre is not None
        assert blockchain_test.blocks is not None
        assert len(blockchain_test.blocks) == 1

    def test_v2_with_multiblock(self, v2_fuzzer_output: FuzzerOutput):
        """Test that v2.0 respects num_blocks parameter."""
        assert v2_fuzzer_output.version == "2.0"

        blockchain_test = blockchain_test_from_fuzzer(
            v2_fuzzer_output,
            Prague,
            num_blocks=3,
            block_strategy="distribute",
        )

        # v2.0 should create 3 blocks
        assert len(blockchain_test.blocks) == 3

    def test_v3_ignores_v2_params(self, v3_fuzzer_output: FuzzerOutput):
        """Test that v3.0 ignores v2.0-specific parameters with warning."""
        assert v3_fuzzer_output.version == "3.0"

        # Should warn when v2 params are provided
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            blockchain_test = blockchain_test_from_fuzzer(
                v3_fuzzer_output,
                Prague,
                num_blocks=5,  # v2.0-only param
                block_strategy="first-block",  # v2.0-only param
                block_time=20,  # v2.0-only param
            )

            # Check warning was issued
            assert len(w) == 1
            assert "v3.0 format ignores" in str(w[0].message)

        # v3.0 should use blocks from input, not num_blocks
        assert len(blockchain_test.blocks) == 1  # From v3_simple.json

    def test_handles_unknown_version(self):
        """Test that unknown version raises validation error."""
        from pydantic_core import ValidationError

        invalid_data = {
            "version": "99.0",
            "fork": "Prague",
            "chainId": "0x01",
            "accounts": {},
            "transactions": [],
        }

        # Pydantic validates version pattern before routing
        with pytest.raises(ValidationError, match="String should match pattern"):
            fuzzer_output = FuzzerOutput(**invalid_data)


class TestVersionDetection:
    """Test that version detection works correctly."""

    def test_v2_version_field(self):
        """Test v2.0 version field is detected."""
        data = {
            "version": "2.0",
            "fork": "Prague",
            "chainId": "0x01",
            "accounts": {},
            "transactions": [],
            "env": {
                "currentCoinbase": "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
                "currentTimestamp": "0x0c",
                "currentGasLimit": "0x05f5e100",
            },
        }
        fuzzer_output = FuzzerOutput(**data)
        assert fuzzer_output.version == "2.0"

    def test_v3_version_field(self):
        """Test v3.0 version field is detected."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled")

        data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x01",
            "accounts": {},
            "blocks": [],
        }
        fuzzer_output = FuzzerOutput(**data)
        assert fuzzer_output.version == "3.0"

    def test_routing_based_on_version(self):
        """Test routing decision is based solely on version field."""
        # v2.0 data
        v2_data = {
            "version": "2.0",
            "fork": "Prague",
            "chainId": "0x01",
            "accounts": {},
            "transactions": [],
            "env": {
                "currentCoinbase": "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
                "currentTimestamp": "0x0c",
                "currentGasLimit": "0x05f5e100",
            },
        }
        v2_output = FuzzerOutput(**v2_data)

        # Should not raise on v2.0
        test = blockchain_test_from_fuzzer(v2_output, Prague)
        assert test is not None

        # v3.0 data
        if config.enable_v3_format:
            v3_data = {
                "version": "3.0",
                "fork": "Prague",
                "chainId": "0x01",
                "accounts": {},
                "blocks": [
                    {
                        "number": "0x01",
                        "timestamp": "0x0c",
                        "gasLimit": "0x05f5e100",
                        "coinbase": "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
                        "transactions": [],
                    }
                ],
            }
            v3_output = FuzzerOutput(**v3_data)

            # Should not raise on v3.0
            test = blockchain_test_from_fuzzer(v3_output, Prague)
            assert test is not None
