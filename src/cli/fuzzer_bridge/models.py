"""
Pydantic models for fuzzer output format v2.

This module defines Data Transfer Objects (DTOs) for parsing
fuzzer output. These DTOs are intentionally separate from EEST
domain models (Transaction, Account) to maintain clean separation
between external data format and internal representation.

Design Principle:
- DTOs (this file): Parse external JSON-RPC standard format
- Domain Models (EEST): Internal test generation logic
- Converter (converter.py): Explicit transformation between the two
"""

from typing import Annotated, Dict, List, Union

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ethereum_test_base_types import AccessList, Address, Bytes, CamelModel, Hash, HexNumber
from ethereum_test_forks import Fork
from ethereum_test_types import Environment


class FuzzerAccountInput(BaseModel):
    """
    Raw account data from fuzzer output.

    This is a DTO that accepts fuzzer's JSON format without triggering
    EEST's Account validation logic or defaults.
    """

    balance: HexNumber
    nonce: HexNumber = HexNumber(0)
    code: Bytes = Bytes(b"")
    storage: Dict[HexNumber, HexNumber] = Field(default_factory=dict)
    private_key: Hash | None = Field(None, alias="privateKey")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class FuzzerAuthorizationInput(BaseModel):
    """
    Raw authorization tuple from fuzzer output (EIP-7702).

    Accepts fuzzer's camelCase JSON format.
    """

    chain_id: HexNumber = Field(..., alias="chainId")
    address: Address
    nonce: HexNumber
    v: HexNumber  # yParity
    r: HexNumber
    s: HexNumber

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class FuzzerTransactionInput(BaseModel):
    """
    Raw transaction data from fuzzer output.

    This is a DTO that accepts standard Ethereum JSON-RPC transaction format
    without triggering EEST's Transaction.model_post_init logic.

    Key differences from EEST Transaction:
    - Uses "gas" not "gas_limit" (JSON-RPC standard)
    - Uses "data" not "input" (JSON-RPC standard)
    - Uses "from" not "sender" (JSON-RPC standard)
    - No automatic TestAddress injection
    - No automatic transaction type detection
    - No automatic signature handling
    """

    from_: Address = Field(..., alias="from")
    to: Address | None = None
    gas: HexNumber  # Will be mapped to gas_limit in converter
    gas_price: HexNumber | None = Field(None, alias="gasPrice")
    max_fee_per_gas: HexNumber | None = Field(None, alias="maxFeePerGas")
    max_priority_fee_per_gas: HexNumber | None = Field(None, alias="maxPriorityFeePerGas")
    nonce: HexNumber
    data: Bytes = Bytes(b"")  # Will be mapped to data/input in converter
    value: HexNumber = HexNumber(0)
    access_list: List[AccessList] | None = Field(None, alias="accessList")
    blob_versioned_hashes: List[Hash] | None = Field(None, alias="blobVersionedHashes")
    max_fee_per_blob_gas: HexNumber | None = Field(None, alias="maxFeePerBlobGas")
    authorization_list: List[FuzzerAuthorizationInput] | None = Field(
        None, alias="authorizationList"
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class WithdrawalInput(BaseModel):
    """
    Withdrawal data from fuzzer output (EIP-4895).

    Represents a validator withdrawal in v3.0 format.
    Not used in v2.0 - added for v3.0 support.
    """

    index: HexNumber = Field(..., alias="index")
    validator_index: HexNumber = Field(..., alias="validatorIndex")
    address: Address = Field(..., alias="address")
    amount: HexNumber = Field(..., alias="amount")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class ValidBlockInput(BaseModel):
    """
    Valid block data from fuzzer output v3.0.

    Represents a single valid block with complete structure including
    transactions and environment that can be executed by the client.

    This is used for blocks expected to be accepted by the client.
    For blocks expected to be rejected, use InvalidBlockInput.
    """

    transactions: List[FuzzerTransactionInput]

    # Block metadata (Priority 1 - Required)
    number: HexNumber = Field(..., alias="number")
    timestamp: HexNumber = Field(..., alias="timestamp")
    gas_limit: HexNumber = Field(HexNumber(30_000_000), alias="gasLimit")
    coinbase: Address = Field(
        Address("0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"),
        alias="coinbase",
    )

    # EIP-1559 (London+)
    base_fee_per_gas: HexNumber | None = Field(None, alias="baseFeePerGas")

    # EIP-3675 (Merge+)
    mix_hash: Hash | None = Field(None, alias="mixHash")
    difficulty: HexNumber = Field(HexNumber(0), alias="difficulty")

    # EIP-4844 (Cancun+)
    excess_blob_gas: HexNumber | None = Field(None, alias="excessBlobGas")
    blob_gas_used: HexNumber | None = Field(None, alias="blobGasUsed")

    # EIP-4788 (Cancun+)
    parent_beacon_block_root: Hash | None = Field(None, alias="parentBeaconBlockRoot")

    # EIP-4895 (Shapella+)
    withdrawals: List[WithdrawalInput] | None = None

    # Optional fields
    extra_data: Bytes = Field(Bytes(b""), alias="extraData")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


def normalize_goevmlab_exception(value: str) -> str:
    """
    Normalize goevmlab exception names to EEST qualified format.

    Goevmlab uses CamelCase exception names (e.g., "InvalidGasLimit") while
    EEST uses fully qualified UPPER_SNAKE_CASE format (e.g.,
    "BlockException.INVALID_GASLIMIT").

    This validator transforms goevmlab format to EEST format at the DTO
    boundary, allowing the converter to work with pre-normalized strings.

    Examples:
        >>> normalize_goevmlab_exception("InvalidGasLimit")
        "BlockException.INVALID_GASLIMIT"
        >>> normalize_goevmlab_exception("NonceTooLow")
        "TransactionException.NONCE_MISMATCH_TOO_LOW"
        >>> normalize_goevmlab_exception("BlockException.INVALID_STATE_ROOT")
        "BlockException.INVALID_STATE_ROOT"  # Pass through already normalized

    Args:
        value: Exception name from goevmlab (CamelCase) or EEST (qualified)

    Returns:
        Fully qualified EEST exception name

    """
    if not isinstance(value, str):
        return value

    # Already normalized (has prefix and uppercase) - pass through
    if "." in value and value.split(".")[1].isupper():
        return value

    # Explicit mapping for known goevmlab exception names
    # Based on goevmlab output analysis from blocktest-json logs
    goevmlab_to_eest = {
        # Block exceptions (8 cases)
        "InvalidGasLimit": "BlockException.INVALID_GASLIMIT",
        "InvalidBaseFee": "BlockException.INVALID_BASEFEE_PER_GAS",
        "InvalidBlobGas": "BlockException.INCORRECT_BLOB_GAS_USED",
        "InvalidBlockNumber": "BlockException.INVALID_BLOCK_NUMBER",
        "InvalidExcessBlobGas": "BlockException.INCORRECT_EXCESS_BLOB_GAS",
        "InvalidTimestamp": "BlockException.INVALID_BLOCK_TIMESTAMP_OLDER_THAN_PARENT",
        # Transaction exceptions (2 cases)
        "NonceTooLow": "TransactionException.NONCE_MISMATCH_TOO_LOW",
        "InsufficientFunds": "TransactionException.INSUFFICIENT_ACCOUNT_FUNDS",
    }

    return goevmlab_to_eest.get(value, value)


GoevmlabExceptionValidator = BeforeValidator(normalize_goevmlab_exception)
"""Pydantic BeforeValidator that normalizes goevmlab exception names to EEST format."""


class InvalidBlockInput(BaseModel):
    """
    Invalid block data from fuzzer output v3.0.

    Represents a block that violates consensus rules and is expected
    to be rejected by the client.

    Two formats supported:
    1. Structured format (PRIMARY): Contains block field with ValidBlockInput structure
       - Allows EEST to run t8n and compute correct state roots
       - Used for field-level validation tests (timestamp, gasLimit, etc.)
    2. RLP format (LEGACY): Contains rlp field with pre-encoded bytes
       - Used only for RLP-corruption tests

    Exactly one of `block` or `rlp` must be present.
    """

    # Block number (REQUIRED for ordering)
    number: HexNumber = Field(..., alias="number")

    # Expected exception (REQUIRED - marks block as invalid)
    # Supports single string or pipe-separated list: "Exception1|Exception2"
    expect_exception: Annotated[str | List[str], GoevmlabExceptionValidator] = Field(
        ...,
        alias="expectException",
        description="Expected exception(s) when client rejects block. "
        "Pipe-separated for multiple: 'BlockException.EXC1|BlockException.EXC2'",
    )

    # Structured block data (PRIMARY format for field-level mutations)
    block: "ValidBlockInput | None" = Field(
        None,
        alias="block",
        description="Structured V3Block data for field-level validation tests",
    )

    # Optional RLP-encoded block (LEGACY format for RLP corruption)
    rlp: Bytes | None = Field(
        None,
        alias="rlp",
        description="RLP-encoded block for direct client testing",
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        # Allow block field now (removed extra = "forbid")

    @model_validator(mode="after")
    def validate_exception_format(self) -> "InvalidBlockInput":
        """Validate expectException is not empty and block/rlp exclusivity."""
        if not self.expect_exception:
            raise ValueError("expectException cannot be empty")

        # Handle list validation
        if isinstance(self.expect_exception, list):
            if not self.expect_exception:
                raise ValueError("expectException list cannot be empty")
            for exc in self.expect_exception:
                if not exc or (isinstance(exc, str) and not exc.strip()):
                    raise ValueError("expectException list items cannot be empty")

        # Exactly one of block or rlp must be set
        if self.block is None and self.rlp is None:
            raise ValueError("Invalid block must have either 'block' or 'rlp' field")
        if self.block is not None and self.rlp is not None:
            raise ValueError("Invalid block cannot have both 'block' and 'rlp' fields")

        return self


# Discriminated union for block input (valid or invalid)
BlockInput = Annotated[
    Union[ValidBlockInput, InvalidBlockInput],
    Field(discriminator=None),  # Auto-discriminate based on fields
]


# Backward compatibility alias
FuzzerBlockInput = ValidBlockInput


class FuzzerGenesisInput(BaseModel):
    """
    Genesis parameters from fuzzer output v3.0.

    Provides explicit genesis values instead of deriving from first block.
    """

    gas_limit: HexNumber = Field(..., alias="gasLimit")
    timestamp: HexNumber = Field(..., alias="timestamp")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class FuzzerOutput(CamelModel):
    """
    Main fuzzer output format (supports v2.0 and v3.0).

    Version 2.0: Uses flat transactions + single env
    Version 3.0: Uses blocks array with per-block env

    This is the top-level DTO that parses the complete fuzzer
    output JSON. It uses pure DTOs (FuzzerAccountInput,
    FuzzerTransactionInput) to avoid triggering EEST domain
    model logic during parsing.

    After parsing, the converter will transform these DTOs into
    EEST domain models.
    """

    version: str = Field(..., pattern="^(2\\.0|3\\.0)$")
    fork: Fork
    chain_id: HexNumber = Field(HexNumber(1))
    accounts: Dict[Address, FuzzerAccountInput]

    # v2.0 fields (deprecated in v3.0)
    transactions: List[FuzzerTransactionInput] | None = None
    env: Environment | None = None
    parent_beacon_block_root: Hash | None = None

    # v3.0 fields (not supported in v2.0)
    blocks: List[BlockInput] | None = None
    genesis: FuzzerGenesisInput | None = None

    @model_validator(mode="after")
    def validate_version_fields(self) -> "FuzzerOutput":
        """Ensure fields match version."""
        from .config import config

        if self.version == "2.0":
            # v2.0: Must have transactions + env, no blocks
            if self.transactions is None:
                raise ValueError("v2.0 format requires 'transactions' field")
            if self.env is None:
                raise ValueError("v2.0 format requires 'env' field")
            if self.blocks is not None:
                raise ValueError("v2.0 format cannot have 'blocks' field")

        elif self.version == "3.0":
            # v3.0: Must have blocks + genesis, no flat transactions/env
            if not config.enable_v3_format:
                raise ValueError(
                    "v3.0 format not enabled. Set FUZZER_BRIDGE_V3=true to enable."
                )
            if self.blocks is None:
                raise ValueError("v3.0 format requires 'blocks' field")
            if self.genesis is None:
                raise ValueError("v3.0 format requires 'genesis' field")
            if self.transactions is not None:
                raise ValueError("v3.0 format cannot have 'transactions' field")
            if self.env is not None:
                raise ValueError("v3.0 format cannot have 'env' field")

        return self
