"""Early version detection for fuzzer formats."""

import json
from pathlib import Path
from typing import Any, Literal


def detect_version(data: dict[str, Any]) -> Literal["2.0", "3.0"]:
    """
    Detect fuzzer format version from raw data.

    This function performs early version detection without full parsing,
    allowing version-specific routing before expensive validation.

    Args:
        data: Raw fuzzer output dictionary

    Returns:
        Version string ("2.0" or "3.0")

    Raises:
        ValueError: If version field is missing or unsupported

    """
    if "version" not in data:
        raise ValueError("Missing version field in fuzzer output")

    version = data["version"]
    if version not in ["2.0", "3.0"]:
        raise ValueError(f"Unsupported version: {version}. Supported: 2.0, 3.0")

    return version  # type: ignore[return-value]


def detect_from_file(file_path: Path) -> Literal["2.0", "3.0"]:
    """
    Detect version from file without full parsing.

    Reads only the version field from the file for efficient routing.

    Args:
        file_path: Path to fuzzer output JSON file

    Returns:
        Version string ("2.0" or "3.0")

    Raises:
        ValueError: If version field is missing or unsupported
        json.JSONDecodeError: If file contains invalid JSON

    """
    with open(file_path) as f:
        data = json.load(f)
    return detect_version(data)
