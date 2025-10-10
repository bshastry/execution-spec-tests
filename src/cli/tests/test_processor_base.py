"""Tests for processor base infrastructure."""

import pytest

from ..fuzzer_bridge.processors.base import FuzzerProcessor


class TestProcessorInterface:
    """Test processor interface and base class."""

    def test_processor_interface_is_defined(self):
        """Test that processor interface is properly defined."""
        # FuzzerProcessor should be an abstract base class
        assert hasattr(FuzzerProcessor, "__abstractmethods__")
        assert "get_cli_params" in FuzzerProcessor.__abstractmethods__
        assert "process" in FuzzerProcessor.__abstractmethods__
        assert "validate_params" in FuzzerProcessor.__abstractmethods__

    def test_cannot_instantiate_abstract_processor(self):
        """Test that abstract processor cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            FuzzerProcessor()  # type: ignore[abstract]

    def test_concrete_processor_can_be_created(self):
        """Test that concrete implementation can be instantiated."""

        class TestProcessor(FuzzerProcessor):
            """Test implementation."""

            def get_cli_params(self):
                return {}

            def process(self, data, **kwargs):
                return {"test": "result"}

            def validate_params(self, **kwargs):
                pass

        processor = TestProcessor()
        assert processor.get_cli_params() == {}
        assert processor.process({}) == {"test": "result"}
        processor.validate_params()  # Should not raise


class TestProcessorValidation:
    """Test parameter validation."""

    def test_processor_validates_params(self):
        """Test parameter validation in processor."""

        class ValidatingProcessor(FuzzerProcessor):
            """Processor with validation."""

            def get_cli_params(self):
                return {"required_param": {"type": str}}

            def process(self, data, **kwargs):
                return {}

            def validate_params(self, **kwargs):
                if "required_param" not in kwargs:
                    raise ValueError("required_param is required")

        processor = ValidatingProcessor()

        # Should not raise for valid params
        processor.validate_params(required_param="value")

        # Should raise for missing required param
        with pytest.raises(ValueError, match="required_param is required"):
            processor.validate_params()
