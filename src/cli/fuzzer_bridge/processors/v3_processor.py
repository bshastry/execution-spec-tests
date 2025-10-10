"""V3 processor for fuzzer format 3.0."""

import warnings
from typing import Any

from ethereum_test_fixtures import BlockchainFixture

from ..config import config
from ..converter import blockchain_test_from_fuzzer_v3
from ..models import FuzzerOutput
from .base import FuzzerProcessor


class V3Processor(FuzzerProcessor):
    """
    Processor for v3.0 fuzzer format.

    V3 format provides explicit block structure with transactions
    already distributed, so no block distribution parameters are needed.
    """

    def get_cli_params(self) -> dict[str, Any]:
        """
        Return v3-specific CLI parameters.

        V3 has no block distribution parameters since blocks
        are explicitly defined in the input.
        """
        return {}  # No v2-style params

    def validate_params(self, **kwargs: Any) -> None:
        """
        Validate v3-specific parameters.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ValueError: If fork parameter is missing

        """
        if "fork" not in kwargs:
            raise ValueError("fork parameter is required")

        # Warn if v2 params are present
        v2_params = ["num_blocks", "block_strategy", "random_blocks", "block_time"]
        used_v2_params = [p for p in v2_params if p in kwargs and kwargs[p] is not None]
        if used_v2_params:
            warnings.warn(
                f"v3.0 format ignores v2 parameters: {used_v2_params}",
                UserWarning,
                stacklevel=2,
            )

    def process(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Process v3.0 format with explicit blocks.

        Args:
            data: Raw v3.0 fuzzer output
            **kwargs: Must include fork and t8n

        Returns:
            Blocktest fixture as dictionary

        Raises:
            ValueError: If v3.0 format not enabled

        """
        # Check if v3 is enabled
        if not config.enable_v3_format:
            raise ValueError("v3.0 format not enabled. Set FUZZER_BRIDGE_V3=true to enable.")

        # Validate parameters
        self.validate_params(**kwargs)

        # Parse v3 data
        fuzzer_output = FuzzerOutput(**data)

        # Use v3 converter (no block distribution params)
        test = blockchain_test_from_fuzzer_v3(
            fuzzer_output,
            fork=kwargs["fork"],
        )

        # Generate fixture
        fixture = test.generate(
            t8n=kwargs["t8n"],
            fork=kwargs["fork"],
            fixture_format=BlockchainFixture,
        )

        return fixture.model_dump(exclude_none=True, by_alias=True, mode="json")
