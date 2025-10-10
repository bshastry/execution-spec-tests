"""V2 processor for fuzzer format 2.0."""

from typing import Any

from ethereum_test_fixtures import BlockchainFixture

from ..converter import blockchain_test_from_fuzzer_v2
from ..models import FuzzerOutput
from .base import FuzzerProcessor


class V2Processor(FuzzerProcessor):
    """
    Processor for v2.0 fuzzer format.

    V2 format provides a flat transaction list and requires
    distribution across multiple blocks via CLI parameters.
    """

    def get_cli_params(self) -> dict[str, Any]:
        """
        Return v2-specific CLI parameters.

        V2 requires block distribution parameters since transactions
        are provided as a flat list.
        """
        return {
            "num_blocks": {"type": int, "default": 1, "help": "Number of blocks to generate"},
            "block_strategy": {
                "type": str,
                "default": "distribute",
                "help": "Transaction distribution strategy",
                "choices": ["distribute", "first-block"],
            },
            "block_time": {"type": int, "default": 12, "help": "Seconds between blocks"},
            "random_blocks": {
                "type": bool,
                "default": False,
                "help": "Use random block count",
            },
        }

    def validate_params(self, **kwargs: Any) -> None:
        """
        Validate v2-specific parameters.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ValueError: If fork parameter is missing

        """
        if "fork" not in kwargs:
            raise ValueError("fork parameter is required")

    def process(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Process v2.0 format with transaction distribution.

        Args:
            data: Raw v2.0 fuzzer output
            **kwargs: Must include fork and t8n, optionally includes
                     num_blocks, block_strategy, block_time, random_blocks

        Returns:
            Blocktest fixture as dictionary

        """
        # Validate parameters
        self.validate_params(**kwargs)

        # Parse v2 data
        fuzzer_output = FuzzerOutput(**data)

        # Extract v2-specific params
        num_blocks = kwargs.get("num_blocks", 1)
        block_strategy = kwargs.get("block_strategy", "distribute")
        block_time = kwargs.get("block_time", 12)
        random_blocks = kwargs.get("random_blocks", False)

        # Handle random blocks
        if random_blocks:
            from ..blocktest_builder import choose_random_num_blocks

            actual_num_blocks = choose_random_num_blocks(
                len(fuzzer_output.transactions or [])
            )
        else:
            actual_num_blocks = num_blocks

        # Use existing v2 converter
        test = blockchain_test_from_fuzzer_v2(
            fuzzer_output,
            fork=kwargs["fork"],
            num_blocks=actual_num_blocks,
            block_strategy=block_strategy,
            block_time=block_time,
        )

        # Generate fixture
        fixture = test.generate(
            t8n=kwargs["t8n"],
            fork=kwargs["fork"],
            fixture_format=BlockchainFixture,
        )

        return fixture.model_dump(exclude_none=True, by_alias=True, mode="json")
