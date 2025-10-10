"""Abstract base class for version-specific fuzzer processors."""

from abc import ABC, abstractmethod
from typing import Any


class FuzzerProcessor(ABC):
    """
    Abstract base for version-specific processors.

    Each processor handles a specific fuzzer format version,
    managing CLI parameters, validation, and conversion logic.
    """

    @abstractmethod
    def get_cli_params(self) -> dict[str, Any]:
        """
        Get version-specific CLI parameters.

        Returns:
            Dictionary of parameter definitions for CLI integration.
            Each key is a parameter name, value is a dict with:
            - type: Parameter type
            - default: Default value
            - help: Help text
            - choices: Optional list of valid choices

        """
        pass

    @abstractmethod
    def process(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Process fuzzer data to blocktest fixture.

        Args:
            data: Raw fuzzer output dictionary
            **kwargs: Additional parameters (fork, t8n, etc.)

        Returns:
            Blocktest fixture as dictionary

        """
        pass

    @abstractmethod
    def validate_params(self, **kwargs: Any) -> None:
        """
        Validate parameters for this processor.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ValueError: If parameters are invalid

        """
        pass
