"""Tests for V2 processor."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ethereum_test_forks import Prague

from ..fuzzer_bridge.models import FuzzerOutput
from ..fuzzer_bridge.processors.v2_processor import V2Processor


class TestV2ProcessorCLIParams:
    """Test V2 processor CLI parameters."""

    def test_v2_processor_cli_params(self):
        """Test V2 processor returns correct CLI parameters."""
        processor = V2Processor()
        params = processor.get_cli_params()

        assert "num_blocks" in params
        assert params["num_blocks"]["default"] == 1
        assert "block_strategy" in params
        assert params["block_strategy"]["default"] == "distribute"
        assert "random_blocks" in params
        assert params["random_blocks"]["default"] is False
        assert "block_time" in params
        assert params["block_time"]["default"] == 12


class TestV2ProcessorValidation:
    """Test V2 processor validation."""

    def test_v2_processor_validates_fork_required(self):
        """Test V2 processor requires fork parameter."""
        processor = V2Processor()

        # Should raise if fork missing
        with pytest.raises(ValueError, match="fork parameter is required"):
            processor.validate_params()

    def test_v2_processor_accepts_valid_params(self):
        """Test V2 processor accepts valid parameters."""
        processor = V2Processor()

        # Should not raise
        processor.validate_params(
            fork=Prague, num_blocks=2, block_strategy="distribute", block_time=12
        )


class TestV2ProcessorIntegration:
    """Test V2 processor integration with converter."""

    @pytest.fixture
    def v2_test_data(self) -> dict:
        """Load v2.0 test vector."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            return json.load(f)

    def test_v2_processor_uses_existing_converter(self, v2_test_data):
        """Test V2 processor delegates to existing converter."""
        processor = V2Processor()

        # Mock t8n
        mock_t8n = Mock()

        # Process should work with real converter
        with patch("cli.fuzzer_bridge.processors.v2_processor.BlockchainFixture") as mock_fixture:
            # Setup mock fixture
            mock_fixture_instance = Mock()
            mock_fixture_instance.model_dump.return_value = {"fixture": "data"}

            # Mock test.generate to return our mock fixture
            with patch(
                "cli.fuzzer_bridge.processors.v2_processor.blockchain_test_from_fuzzer_v2"
            ) as mock_conv:
                mock_test = Mock()
                mock_test.generate.return_value = mock_fixture_instance
                mock_conv.return_value = mock_test

                result = processor.process(
                    v2_test_data, fork=Prague, t8n=mock_t8n, num_blocks=2
                )

                # Verify converter was called
                mock_conv.assert_called_once()
                call_kwargs = mock_conv.call_args.kwargs
                assert call_kwargs["num_blocks"] == 2
                assert call_kwargs["fork"] == Prague

                # Verify we got fixture data back
                assert result == {"fixture": "data"}
