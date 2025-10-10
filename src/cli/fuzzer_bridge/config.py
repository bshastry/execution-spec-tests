"""Feature flags for fuzzer bridge."""

import os
from dataclasses import dataclass


@dataclass
class FuzzerBridgeConfig:
    """Configuration for fuzzer bridge features."""

    # Feature flags
    enable_v3_format: bool = False  # Default: disabled
    strict_version_validation: bool = True
    use_version_processors: bool = False  # Default: use old path

    @classmethod
    def from_env(cls) -> "FuzzerBridgeConfig":
        """Load configuration from environment variables."""
        return cls(
            enable_v3_format=os.getenv("FUZZER_BRIDGE_V3", "false").lower() == "true",
            strict_version_validation=os.getenv("FUZZER_STRICT_VERSION", "true").lower()
            == "true",
            use_version_processors=os.getenv("FUZZER_USE_PROCESSORS", "false").lower()
            == "true",
        )


# Global config instance
config = FuzzerBridgeConfig.from_env()
