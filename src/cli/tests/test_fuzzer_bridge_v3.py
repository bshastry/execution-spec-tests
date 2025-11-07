"""Tests for v3.0 fuzzer format (feature-flagged)."""

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from ethereum_test_base_types import Address, HexNumber
from ethereum_test_forks import Prague

from ..fuzzer_bridge.config import FuzzerBridgeConfig
from ..fuzzer_bridge.models import (
    FuzzerBlockInput,
    FuzzerOutput,
    InvalidBlockInput,
    ValidBlockInput,
    WithdrawalInput,
)


def load_v3_vector(filename: str) -> Dict[str, Any]:
    """Load v3.0 test vector from vectors/ directory."""
    vector_path = Path(__file__).parent / "vectors" / filename
    with open(vector_path) as f:
        return json.load(f)


# Mark all tests in this file to skip if v3.0 not enabled
pytestmark = pytest.mark.skipif(
    not FuzzerBridgeConfig.from_env().enable_v3_format,
    reason="v3.0 support not enabled (set FUZZER_BRIDGE_V3=true)",
)


class TestV3ModelParsing:
    """Test v3.0 model parsing with feature flag enabled."""

    def test_v3_version_accepted(self):
        """Test v3.0 version is accepted when flag enabled."""
        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")

        # Should not raise with feature flag enabled
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert fuzzer_output.version == "3.0"
        assert fuzzer_output.blocks is not None
        assert len(fuzzer_output.blocks) == 1

    def test_v3_requires_blocks(self):
        """Test v3.0 format requires blocks field."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            # Missing 'blocks' field
        }

        with pytest.raises(ValidationError, match="requires 'blocks' field"):
            FuzzerOutput(**fuzzer_data)

    def test_v3_forbids_flat_transactions(self):
        """Test v3.0 format cannot have flat transactions."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [],
            "transactions": [],  # Not allowed in v3.0
        }

        with pytest.raises(ValidationError, match="cannot have 'transactions' field"):
            FuzzerOutput(**fuzzer_data)

    def test_v3_forbids_env(self):
        """Test v3.0 format cannot have flat env."""
        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")
        fuzzer_data["env"] = {
            "currentCoinbase": "0x2000000000000000000000000000000000000001",
            "currentDifficulty": "0x0",
            "currentGasLimit": "0x1c9c380",
            "currentNumber": "0x1",
            "currentTimestamp": "0x3e8",
        }

        with pytest.raises(ValidationError, match="cannot have 'env' field"):
            FuzzerOutput(**fuzzer_data)

    def test_v3_block_input_parsing(self):
        """Test FuzzerBlockInput parses correctly."""
        block_data = {
            "number": "0x1",
            "timestamp": "0x3e8",
            "gasLimit": "0x1c9c380",
            "coinbase": "0x2000000000000000000000000000000000000001",
            "baseFeePerGas": "0x7",
            "difficulty": "0x0",
            "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "transactions": [],
        }

        block = FuzzerBlockInput(**block_data)

        assert block.number == 1
        assert block.timestamp == 1000
        assert block.gas_limit == 30_000_000
        assert block.coinbase == Address("0x2000000000000000000000000000000000000001")

    def test_v3_withdrawal_input_parsing(self):
        """Test WithdrawalInput parses correctly."""
        withdrawal_data = {
            "index": "0x0",
            "validatorIndex": "0x64",
            "address": "0x4000000000000000000000000000000000000001",
            "amount": "0x1bc16d674ec80000",
        }

        withdrawal = WithdrawalInput(**withdrawal_data)

        assert withdrawal.index == 0
        assert withdrawal.validator_index == 100
        assert withdrawal.address == Address("0x4000000000000000000000000000000000000001")
        assert withdrawal.amount == HexNumber(2000000000000000000)

    def test_v3_simple_vector_parses(self):
        """Test simple v3.0 test vector parses completely."""
        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert fuzzer_output.version == "3.0"
        assert fuzzer_output.fork == Prague
        assert len(fuzzer_output.blocks) == 1
        assert len(fuzzer_output.blocks[0].transactions) == 1
        assert fuzzer_output.blocks[0].base_fee_per_gas == HexNumber(7)

    def test_v3_multi_block_vector_parses(self):
        """Test multi-block v3.0 test vector parses."""
        fuzzer_data = load_v3_vector("fuzzer_test_v3_multi.json")

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert fuzzer_output.version == "3.0"
        assert len(fuzzer_output.blocks) == 3
        # Verify timestamps increment
        assert fuzzer_output.blocks[0].timestamp < fuzzer_output.blocks[1].timestamp
        assert fuzzer_output.blocks[1].timestamp < fuzzer_output.blocks[2].timestamp

    def test_v3_withdrawals_vector_parses(self):
        """Test v3.0 test vector with withdrawals parses."""
        fuzzer_data = load_v3_vector("fuzzer_test_v3_withdrawals.json")

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert fuzzer_output.version == "3.0"
        assert fuzzer_output.blocks[0].withdrawals is not None
        assert len(fuzzer_output.blocks[0].withdrawals) == 2

        # Verify withdrawal indices are sequential
        assert fuzzer_output.blocks[0].withdrawals[0].index == 0
        assert fuzzer_output.blocks[0].withdrawals[1].index == 1


class TestV3FieldMapping:
    """Test field mapping from JSON to Python models."""

    def test_camel_case_to_snake_case(self):
        """Test camelCase JSON fields map to snake_case Python."""
        block_data = {
            "number": "0x1",
            "timestamp": "0x3e8",
            "gasLimit": "0x1c9c380",  # JSON: gasLimit
            "coinbase": "0x2000000000000000000000000000000000000001",
            "baseFeePerGas": "0x7",  # JSON: baseFeePerGas
            "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "transactions": [],
        }

        block = FuzzerBlockInput(**block_data)

        # Python: snake_case
        assert block.gas_limit == 30_000_000
        assert block.base_fee_per_gas == HexNumber(7)
        assert hasattr(block, "mix_hash")

    def test_withdrawal_field_mapping(self):
        """Test withdrawal field mapping."""
        withdrawal_data = {
            "index": "0x0",
            "validatorIndex": "0x64",  # JSON: validatorIndex
            "address": "0x4000000000000000000000000000000000000001",
            "amount": "0x1bc16d674ec80000",
        }

        withdrawal = WithdrawalInput(**withdrawal_data)

        # Python: snake_case
        assert withdrawal.validator_index == 100


class TestV3Converter:
    """Test v3.0 converter functionality."""

    def test_convert_simple_block(self):
        """Test conversion of simple single-block test."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        assert len(blockchain_test.blocks) == 1
        assert len(blockchain_test.blocks[0].txs) == 1
        assert blockchain_test.genesis_environment.number == 0

    def test_convert_multi_block(self):
        """Test conversion of multi-block test."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_multi.json")
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        assert len(blockchain_test.blocks) == 3
        # Validate timestamps increment
        for i in range(len(blockchain_test.blocks) - 1):
            assert blockchain_test.blocks[i + 1].timestamp > blockchain_test.blocks[i].timestamp

    def test_convert_with_withdrawals(self):
        """Test conversion with withdrawals."""
        from ethereum_test_forks import Cancun

        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_withdrawals.json")
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Cancun)

        assert blockchain_test.blocks[0].withdrawals is not None
        assert len(blockchain_test.blocks[0].withdrawals) == 2

    def test_genesis_derivation(self):
        """Test genesis block is correctly derived."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        genesis = blockchain_test.genesis_environment
        first_block = blockchain_test.blocks[0]

        assert genesis.number == 0
        assert genesis.timestamp == first_block.timestamp - 12
        assert genesis.gas_limit == first_block.gas_limit

    def test_per_block_beacon_roots(self):
        """Test per-block beacon roots (EIP-4788)."""
        from ethereum_test_forks import Cancun

        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_withdrawals.json")
        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Cancun)

        # Each block can have its own beacon root
        assert blockchain_test.blocks[0].parent_beacon_block_root is not None


class TestV3Validations:
    """Test critical validations from validation report."""

    def test_withdrawal_index_gap_detected(self):
        """Test withdrawal index gap is detected (Section 5.2)."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_withdrawals.json")
        # Create gap: index 0 → index 5 (missing 1-4)
        fuzzer_data["blocks"][0]["withdrawals"][1]["index"] = "0x5"

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        with pytest.raises(ValueError, match="withdrawal index"):
            blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

    def test_genesis_timestamp_too_low(self):
        """Test genesis timestamp validation (Section 5.3)."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")
        # Set first block timestamp < 12
        fuzzer_data["blocks"][0]["timestamp"] = "0x5"  # 5 seconds

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        with pytest.raises(ValueError, match="must be >= 12"):
            blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

    def test_genesis_timestamp_minimum_valid(self):
        """Test minimum valid genesis timestamp."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_simple.json")
        # Set first block timestamp = 12 (minimum valid)
        fuzzer_data["blocks"][0]["timestamp"] = "0xc"  # 12 seconds

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        # Genesis timestamp should be 0
        assert blockchain_test.genesis_environment.timestamp == 0

    def test_empty_blocks_allowed(self):
        """Test consecutive empty blocks are allowed."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = load_v3_vector("fuzzer_test_v3_multi.json")

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        # Last block is empty
        assert len(blockchain_test.blocks[2].txs) == 0


class TestInvalidBlockSupport:
    """Test invalid block support in v3.0 format."""

    def test_invalid_block_minimal(self):
        """Test InvalidBlockInput with minimal required fields."""
        block_data = {
            "number": "0x1",
            "expectException": "BlockException.INVALID_STATE_ROOT",
        }

        block = InvalidBlockInput(**block_data)

        assert block.number == 1
        assert block.expect_exception == "BlockException.INVALID_STATE_ROOT"
        assert block.rlp is None

    def test_invalid_block_with_rlp(self):
        """Test InvalidBlockInput with optional RLP field."""
        block_data = {
            "number": "0x2",
            "expectException": "BlockException.INVALID_TIMESTAMP",
            "rlp": "0xf90260f901f9a0",
        }

        block = InvalidBlockInput(**block_data)

        assert block.number == 2
        assert block.expect_exception == "BlockException.INVALID_TIMESTAMP"
        assert block.rlp is not None

    def test_invalid_block_rejects_transactions(self):
        """Test that InvalidBlockInput cannot have transactions field."""
        block_data = {
            "number": "0x1",
            "expectException": "BlockException.INVALID_STATE_ROOT",
            "transactions": [],  # Should be rejected
        }

        # Pydantic should reject this as extra field
        with pytest.raises(ValidationError):
            InvalidBlockInput(**block_data)

    def test_invalid_block_rejects_timestamp(self):
        """Test that InvalidBlockInput cannot have timestamp field."""
        block_data = {
            "number": "0x1",
            "expectException": "BlockException.INVALID_STATE_ROOT",
            "timestamp": "0x3e8",  # Should be rejected
        }

        # Pydantic should reject this as extra field
        with pytest.raises(ValidationError):
            InvalidBlockInput(**block_data)

    def test_invalid_block_empty_exception(self):
        """Test that expectException cannot be empty."""
        block_data = {
            "number": "0x1",
            "expectException": "",
        }

        with pytest.raises(ValidationError, match="expectException cannot be empty"):
            InvalidBlockInput(**block_data)

    def test_invalid_block_missing_exception(self):
        """Test that expectException is required."""
        block_data = {
            "number": "0x1",
            # Missing expectException
        }

        with pytest.raises(ValidationError, match="Field required"):
            InvalidBlockInput(**block_data)

    def test_valid_block_backward_compatibility(self):
        """Test that ValidBlockInput works like old FuzzerBlockInput."""
        block_data = {
            "number": "0x1",
            "timestamp": "0x3e8",
            "gasLimit": "0x1c9c380",
            "coinbase": "0x2000000000000000000000000000000000000001",
            "transactions": [],
        }

        # Both should work
        valid_block = ValidBlockInput(**block_data)
        fuzzer_block = FuzzerBlockInput(**block_data)

        assert valid_block.number == fuzzer_block.number
        assert valid_block.timestamp == fuzzer_block.timestamp

    def test_fuzzer_output_with_invalid_block(self):
        """Test FuzzerOutput accepts invalid block."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {
                "0xa94f5374fce5edbc8e2a8697c15331677e6ebf0b": {
                    "balance": "0xde0b6b3a7640000",
                    "nonce": "0x0",
                }
            },
            "blocks": [
                {
                    "number": "0x1",
                    "expectException": "BlockException.INVALID_TIMESTAMP",
                }
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert len(fuzzer_output.blocks) == 1
        assert isinstance(fuzzer_output.blocks[0], InvalidBlockInput)
        assert fuzzer_output.blocks[0].expect_exception == "BlockException.INVALID_TIMESTAMP"

    def test_fuzzer_output_mixed_blocks(self):
        """Test FuzzerOutput with mixed valid and invalid blocks."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {
                "0xa94f5374fce5edbc8e2a8697c15331677e6ebf0b": {
                    "balance": "0xde0b6b3a7640000",
                    "nonce": "0x0",
                }
            },
            "blocks": [
                {
                    "number": "0x1",
                    "timestamp": "0x3e8",
                    "gasLimit": "0x1c9c380",
                    "coinbase": "0x2000000000000000000000000000000000000001",
                    "transactions": [],
                },
                {
                    "number": "0x2",
                    "expectException": "BlockException.INVALID_BLOCK_TIMESTAMP_OLDER_THAN_PARENT",
                },
                {
                    "number": "0x3",
                    "timestamp": "0x7d0",
                    "gasLimit": "0x1c9c380",
                    "coinbase": "0x2000000000000000000000000000000000000001",
                    "transactions": [],
                },
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert len(fuzzer_output.blocks) == 3
        assert isinstance(fuzzer_output.blocks[0], ValidBlockInput)
        assert isinstance(fuzzer_output.blocks[1], InvalidBlockInput)
        assert isinstance(fuzzer_output.blocks[2], ValidBlockInput)

    def test_fuzzer_output_all_invalid_blocks(self):
        """Test FuzzerOutput with only invalid blocks."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [
                {"number": "0x1", "expectException": "BlockException.INVALID_TIMESTAMP"},
                {"number": "0x2", "expectException": "BlockException.INVALID_GAS_LIMIT"},
                {"number": "0x3", "expectException": "TransactionException.NONCE_TOO_LOW"},
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        assert len(fuzzer_output.blocks) == 3
        assert all(isinstance(b, InvalidBlockInput) for b in fuzzer_output.blocks)

    def test_exception_format_variations(self):
        """Test various valid exception format variations."""
        valid_exceptions = [
            "BlockException.INVALID_STATE_ROOT",
            "TransactionException.NONCE_TOO_LOW",
            "INVALID_TIMESTAMP",  # Legacy format
            "BlockException.INVALID_GAS_USED",
            "BlockException.INVALID_BASE_FEE",
        ]

        for exception in valid_exceptions:
            block_data = {
                "number": "0x1",
                "expectException": exception,
            }
            block = InvalidBlockInput(**block_data)
            assert block.expect_exception == exception

    def test_goevmlab_exception_normalization(self):
        """Test BeforeValidator normalizes all goevmlab exception names."""
        # Test all 8 known goevmlab exception names
        goevmlab_mappings = [
            # Block exceptions
            ("InvalidGasLimit", "BlockException.INVALID_GASLIMIT"),
            ("InvalidBaseFee", "BlockException.INVALID_BASEFEE_PER_GAS"),
            ("InvalidBlobGas", "BlockException.INCORRECT_BLOB_GAS_USED"),
            ("InvalidBlockNumber", "BlockException.INVALID_BLOCK_NUMBER"),
            ("InvalidExcessBlobGas", "BlockException.INCORRECT_EXCESS_BLOB_GAS"),
            ("InvalidTimestamp", "BlockException.INVALID_BLOCK_TIMESTAMP_OLDER_THAN_PARENT"),
            # Transaction exceptions
            ("NonceTooLow", "TransactionException.NONCE_MISMATCH_TOO_LOW"),
            ("InsufficientFunds", "TransactionException.INSUFFICIENT_ACCOUNT_FUNDS"),
        ]

        for goevmlab_input, expected_eest in goevmlab_mappings:
            block = InvalidBlockInput(
                number="0x1",
                expectException=goevmlab_input,
            )
            assert block.expect_exception == expected_eest, (
                f"Failed to normalize {goevmlab_input} to {expected_eest}, "
                f"got {block.expect_exception}"
            )

    def test_eest_format_exception_passthrough(self):
        """Test that already-normalized EEST format exceptions pass through unchanged."""
        eest_exceptions = [
            "BlockException.INVALID_STATE_ROOT",
            "BlockException.INVALID_GASLIMIT",
            "TransactionException.INSUFFICIENT_ACCOUNT_FUNDS",
            "TransactionException.NONCE_MISMATCH_TOO_LOW",
        ]

        for eest_format in eest_exceptions:
            block = InvalidBlockInput(
                number="0x1",
                expectException=eest_format,
            )
            assert block.expect_exception == eest_format, (
                f"EEST format {eest_format} should pass through unchanged, "
                f"got {block.expect_exception}"
            )

    def test_mixed_goevmlab_eest_blocks(self):
        """Test FuzzerOutput with mixed goevmlab and EEST exception formats."""
        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {
                "0x1000000000000000000000000000000000000000": {
                    "balance": "0xde0b6b3a7640000",
                    "nonce": "0x0",
                }
            },
            "blocks": [
                {
                    "number": "0x1",
                    "timestamp": "0x3e8",
                    "gasLimit": "0x1c9c380",
                    "coinbase": "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
                    "transactions": [],
                },
                # Goevmlab format
                {"number": "0x2", "expectException": "InvalidGasLimit"},
                # EEST format
                {"number": "0x3", "expectException": "BlockException.INVALID_STATE_ROOT"},
                # Goevmlab format
                {"number": "0x4", "expectException": "NonceTooLow"},
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)
        assert isinstance(fuzzer_output.blocks[0], ValidBlockInput)
        assert isinstance(fuzzer_output.blocks[1], InvalidBlockInput)
        assert fuzzer_output.blocks[1].expect_exception == "BlockException.INVALID_GASLIMIT"
        assert isinstance(fuzzer_output.blocks[2], InvalidBlockInput)
        assert fuzzer_output.blocks[2].expect_exception == "BlockException.INVALID_STATE_ROOT"
        assert isinstance(fuzzer_output.blocks[3], InvalidBlockInput)
        assert (
            fuzzer_output.blocks[3].expect_exception
            == "TransactionException.NONCE_MISMATCH_TOO_LOW"
        )


class TestInvalidBlockConverter:
    """Test converter handles invalid blocks correctly."""

    def test_convert_invalid_block_simple(self):
        """Test converting simple invalid block."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [
                {
                    "number": "0x1",
                    "expectException": "BlockException.INVALID_STATE_ROOT",
                }
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)
        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        assert len(blockchain_test.blocks) == 1
        assert blockchain_test.blocks[0].exception is not None
        # Check exception was parsed correctly
        from ethereum_test_exceptions import BlockException

        assert blockchain_test.blocks[0].exception == BlockException.INVALID_STATE_ROOT

    def test_convert_mixed_valid_invalid_blocks(self):
        """Test converting mix of valid and invalid blocks."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {
                "0xa94f5374fce5edbc8e2a8697c15331677e6ebf0b": {
                    "balance": "0xde0b6b3a7640000",
                    "nonce": "0x0",
                    "privateKey": (
                        "0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"
                    ),
                }
            },
            "blocks": [
                {
                    "number": "0x1",
                    "timestamp": "0x3e8",
                    "gasLimit": "0x1c9c380",
                    "coinbase": "0x2000000000000000000000000000000000000001",
                    "transactions": [],
                },
                {
                    "number": "0x2",
                    "expectException": "BlockException.INVALID_BLOCK_TIMESTAMP_OLDER_THAN_PARENT",
                },
                {
                    "number": "0x3",
                    "timestamp": "0x7d0",
                    "gasLimit": "0x1c9c380",
                    "coinbase": "0x2000000000000000000000000000000000000001",
                    "transactions": [],
                },
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)
        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        assert len(blockchain_test.blocks) == 3
        # Block 0: valid
        assert blockchain_test.blocks[0].exception is None
        assert len(blockchain_test.blocks[0].txs) == 0
        # Block 1: invalid
        from ethereum_test_exceptions import BlockException

        assert (
            blockchain_test.blocks[1].exception
            == BlockException.INVALID_BLOCK_TIMESTAMP_OLDER_THAN_PARENT
        )
        # Block 2: valid
        assert blockchain_test.blocks[2].exception is None

    def test_convert_transaction_exception(self):
        """Test converting block with TransactionException."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [
                {
                    "number": "0x1",
                    "expectException": "TransactionException.NONCE_MISMATCH_TOO_LOW",
                }
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)
        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        from ethereum_test_exceptions import TransactionException

        assert blockchain_test.blocks[0].exception == TransactionException.NONCE_MISMATCH_TOO_LOW

    def test_convert_legacy_exception_format(self):
        """Test converting block with legacy exception format (no prefix)."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [
                {
                    "number": "0x1",
                    "expectException": "INVALID_STATE_ROOT",  # Legacy format (no prefix)
                }
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)
        blockchain_test = blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)

        from ethereum_test_exceptions import BlockException

        assert blockchain_test.blocks[0].exception == BlockException.INVALID_STATE_ROOT

    def test_convert_invalid_exception_string(self):
        """Test that invalid exception strings raise error."""
        from ..fuzzer_bridge.converter import blockchain_test_from_fuzzer_v3

        fuzzer_data = {
            "version": "3.0",
            "fork": "Prague",
            "chainId": "0x1",
            "accounts": {},
            "blocks": [
                {
                    "number": "0x1",
                    "expectException": "UnknownException.INVALID_VALUE",
                }
            ],
        }

        fuzzer_output = FuzzerOutput(**fuzzer_data)

        with pytest.raises(ValueError, match="Unknown exception prefix"):
            blockchain_test_from_fuzzer_v3(fuzzer_output, fork=Prague)
