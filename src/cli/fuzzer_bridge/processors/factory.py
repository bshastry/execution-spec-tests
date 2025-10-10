"""Factory for creating version-specific processors."""

from typing import Literal

from .base import FuzzerProcessor
from .v2_processor import V2Processor
from .v3_processor import V3Processor


class ProcessorFactory:
    """
    Factory to create version-specific processors.

    Provides centralized registry and creation logic for
    version-specific fuzzer processors.
    """

    _processors: dict[str, type[FuzzerProcessor]] = {
        "2.0": V2Processor,
        "3.0": V3Processor,
    }

    @classmethod
    def create_processor(cls, version: Literal["2.0", "3.0"]) -> FuzzerProcessor:
        """
        Create processor for given version.

        Args:
            version: Fuzzer format version ("2.0" or "3.0")

        Returns:
            Processor instance for the specified version

        Raises:
            ValueError: If version is not supported

        """
        if version not in cls._processors:
            supported = ", ".join(cls._processors.keys())
            raise ValueError(f"Unsupported version: {version}. Supported versions: {supported}")
        return cls._processors[version]()

    @classmethod
    def is_version_supported(cls, version: str) -> bool:
        """
        Check if version is supported.

        Args:
            version: Version string to check

        Returns:
            True if version is supported, False otherwise

        """
        return version in cls._processors
