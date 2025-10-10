"""Tests for V3 processor."""

import json
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ethereum_test_forks import Prague

from ..fuzzer_bridge.config import config
from ..fuzzer_bridge.models import FuzzerOutput
from ..fuzzer_bridge.processors.v3_processor import V3Processor


class TestV3ProcessorCLIParams:
    """Test V3 processor CLI parameters."""

    def test_v3_processor_no_block_params(self):
        """Test V3 processor has no block distribution params."""
        processor = V3Processor()
        params = processor.get_cli_params()

        # V3 should not have v2-specific params
        assert "num_blocks" not in params
        assert "block_strategy" not in params
        assert "random_blocks" not in params
        assert "block_time" not in params


class TestV3ProcessorValidation:
    """Test V3 processor validation."""

    def test_v3_processor_validates_fork_required(self):
        """Test V3 processor requires fork parameter."""
        processor = V3Processor()

        # Should raise if fork missing
        with pytest.raises(ValueError, match="fork parameter is required"):
            processor.validate_params()

    def test_v3_processor_warns_on_v2_params(self):
        """Test V3 processor warns when v2 params are provided."""
        processor = V3Processor()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            processor.validate_params(
                fork=Prague,
                num_blocks=5,  # v2 param
                block_strategy="first-block",  # v2 param
            )

            assert len(w) == 1
            assert "v3.0 format ignores v2 parameters" in str(w[0].message)


class TestV3ProcessorIntegration:
    """Test V3 processor integration with converter."""

    @pytest.fixture
    def v3_test_data(self) -> dict:
        """Load v3.0 test vector."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled")

        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_v3_simple.json"
        with open(vector_path) as f:
            return json.load(f)

    def test_v3_processor_requires_v3_enabled(self, v3_test_data):
        """Test V3 processor checks if v3 is enabled."""
        processor = V3Processor()

        # Mock config to disable v3
        with patch("cli.fuzzer_bridge.processors.v3_processor.config") as mock_config:
            mock_config.enable_v3_format = False

            mock_t8n = Mock()

            # Should raise if v3 not enabled
            with pytest.raises(ValueError, match="v3.0 format not enabled"):
                processor.process(v3_test_data, fork=Prague, t8n=mock_t8n)

    def test_v3_processor_uses_v3_converter(self, v3_test_data):
        """Test V3 processor delegates to v3 converter."""
        if not config.enable_v3_format:
            pytest.skip("V3.0 support disabled")

        processor = V3Processor()
        mock_t8n = Mock()

        # Process should work with real converter
        with patch("cli.fuzzer_bridge.processors.v3_processor.BlockchainFixture") as mock_fixture:
            # Setup mock fixture
            mock_fixture_instance = Mock()
            mock_fixture_instance.model_dump.return_value = {"fixture": "data"}

            # Mock test.generate to return our mock fixture
            with patch(
                "cli.fuzzer_bridge.processors.v3_processor.blockchain_test_from_fuzzer_v3"
            ) as mock_conv:
                mock_test = Mock()
                mock_test.generate.return_value = mock_fixture_instance
                mock_conv.return_value = mock_test

                result = processor.process(v3_test_data, fork=Prague, t8n=mock_t8n)

                # Verify converter was called without block params
                mock_conv.assert_called_once()
                call_kwargs = mock_conv.call_args.kwargs
                assert "num_blocks" not in call_kwargs
                assert "block_strategy" not in call_kwargs
                assert call_kwargs["fork"] == Prague

                # Verify we got fixture data back
                assert result == {"fixture": "data"}
