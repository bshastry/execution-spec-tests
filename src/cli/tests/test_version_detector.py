"""Tests for version detection."""

import json
import pytest
from pathlib import Path

from ..fuzzer_bridge.version_detector import detect_version, detect_from_file


class TestVersionDetector:
    """Test version detection from data."""

    def test_detects_v2_version(self):
        """Test detection of v2.0 version."""
        data = {"version": "2.0"}
        assert detect_version(data) == "2.0"

    def test_detects_v3_version(self):
        """Test detection of v3.0 version."""
        data = {"version": "3.0"}
        assert detect_version(data) == "3.0"

    def test_raises_on_invalid_version(self):
        """Test that invalid version raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported version"):
            detect_version({"version": "99.0"})

    def test_raises_on_missing_version(self):
        """Test that missing version raises ValueError."""
        with pytest.raises(ValueError, match="Missing version"):
            detect_version({})


class TestFileBasedDetection:
    """Test version detection from files."""

    def test_detect_from_file_v2(self, tmp_path):
        """Test detecting v2.0 from file."""
        file = tmp_path / "v2.json"
        file.write_text('{"version": "2.0"}')
        assert detect_from_file(file) == "2.0"

    def test_detect_from_file_v3(self, tmp_path):
        """Test detecting v3.0 from file."""
        file = tmp_path / "v3.json"
        file.write_text('{"version": "3.0"}')
        assert detect_from_file(file) == "3.0"

    def test_detect_from_file_missing_version(self, tmp_path):
        """Test that file without version raises error."""
        file = tmp_path / "no_version.json"
        file.write_text('{"fork": "Prague"}')
        with pytest.raises(ValueError, match="Missing version"):
            detect_from_file(file)

    def test_detect_from_file_invalid_json(self, tmp_path):
        """Test that invalid JSON raises appropriate error."""
        file = tmp_path / "invalid.json"
        file.write_text('not valid json')
        with pytest.raises(json.JSONDecodeError):
            detect_from_file(file)
