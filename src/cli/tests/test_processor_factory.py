"""Tests for processor factory."""

import pytest

from ..fuzzer_bridge.processors.factory import ProcessorFactory
from ..fuzzer_bridge.processors.v2_processor import V2Processor
from ..fuzzer_bridge.processors.v3_processor import V3Processor


class TestProcessorFactory:
    """Test processor factory creation."""

    def test_factory_creates_v2_processor(self):
        """Test factory creates V2 processor."""
        processor = ProcessorFactory.create_processor("2.0")
        assert isinstance(processor, V2Processor)

    def test_factory_creates_v3_processor(self):
        """Test factory creates V3 processor."""
        processor = ProcessorFactory.create_processor("3.0")
        assert isinstance(processor, V3Processor)

    def test_factory_raises_on_unknown_version(self):
        """Test factory raises on unknown version."""
        with pytest.raises(ValueError, match="Unsupported version"):
            ProcessorFactory.create_processor("99.0")  # type: ignore[arg-type]

    def test_is_version_supported_v2(self):
        """Test version support check for v2."""
        assert ProcessorFactory.is_version_supported("2.0")

    def test_is_version_supported_v3(self):
        """Test version support check for v3."""
        assert ProcessorFactory.is_version_supported("3.0")

    def test_is_version_not_supported(self):
        """Test version support check for unsupported version."""
        assert not ProcessorFactory.is_version_supported("99.0")

    def test_factory_has_version_registry(self):
        """Test factory maintains version registry."""
        registry = ProcessorFactory._processors
        assert "2.0" in registry
        assert "3.0" in registry
        assert registry["2.0"] == V2Processor
        assert registry["3.0"] == V3Processor
