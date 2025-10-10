"""Tests for BlocktestBuilder with processor integration."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ethereum_test_forks import Prague

from ..fuzzer_bridge.blocktest_builder import BlocktestBuilder


class TestBlocktestBuilderWithProcessors:
    """Test BlocktestBuilder with processor feature flag."""

    @pytest.fixture
    def v2_test_data(self) -> dict:
        """Load v2.0 test vector."""
        vector_path = Path(__file__).parent / "vectors" / "fuzzer_test_0.json"
        with open(vector_path) as f:
            return json.load(f)

    def test_builder_uses_old_path_when_disabled(self, v2_test_data):
        """Test builder uses old converter when feature flag is disabled."""
        builder = BlocktestBuilder()

        # Ensure processors are disabled
        with patch("cli.fuzzer_bridge.blocktest_builder.config") as mock_config:
            mock_config.use_version_processors = False

            # Should use old converter
            with patch(
                "cli.fuzzer_bridge.blocktest_builder.blockchain_test_from_fuzzer"
            ) as mock_converter:
                # Setup mock
                mock_test = Mock()
                mock_fixture = Mock()
                mock_fixture.model_dump.return_value = {"test": "fixture"}
                mock_test.generate.return_value = mock_fixture
                mock_converter.return_value = mock_test

                result = builder.build_blocktest(v2_test_data)

                # Should use old converter
                mock_converter.assert_called_once()
                assert result == {"test": "fixture"}

    def test_builder_uses_processor_when_enabled(self, v2_test_data):
        """Test builder uses processor when feature flag is enabled."""
        builder = BlocktestBuilder()

        # Enable processors
        with patch("cli.fuzzer_bridge.blocktest_builder.config") as mock_config:
            mock_config.use_version_processors = True

            # Mock the processor path - detect_version is in version_detector module
            with patch("cli.fuzzer_bridge.version_detector.detect_version") as mock_detect:
                mock_detect.return_value = "2.0"

                # ProcessorFactory is in the processors.factory module
                with patch(
                    "cli.fuzzer_bridge.processors.factory.ProcessorFactory"
                ) as mock_factory:
                    # Setup mock processor
                    mock_processor = Mock()
                    mock_processor.process.return_value = {"processor": "result"}
                    mock_factory.create_processor.return_value = mock_processor

                    result = builder.build_blocktest(v2_test_data, num_blocks=2)

                    # Should detect version
                    mock_detect.assert_called_once()

                    # Should create processor
                    mock_factory.create_processor.assert_called_once_with("2.0")

                    # Should use processor
                    mock_processor.process.assert_called_once()
                    call_kwargs = mock_processor.process.call_args.kwargs
                    assert call_kwargs["num_blocks"] == 2

                    assert result == {"processor": "result"}
