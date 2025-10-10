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

from typing import Dict, List

from pydantic import BaseModel, Field, model_validator

from ethereum_test_base_types import AccessList, Address, Bytes, CamelModel, Hash, HexNumber
from ethereum_test_forks import Fork
from ethereum_test_types import Environment
from ethereum_test_types import Withdrawal as EESTWithdrawal


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


class FuzzerBlockInput(BaseModel):
    """
    Block data from fuzzer output v3.0.

    Represents a single block with its transactions and environment.
    Not used in v2.0 - added for v3.0 support.

    In v3.0, the fuzzer specifies complete block structure including
    per-block environment parameters. This gives the fuzzer full control
    over block boundaries and block-specific parameters.
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
    blocks: List[FuzzerBlockInput] | None = None

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
            # v3.0: Must have blocks, no flat transactions/env
            if not config.enable_v3_format:
                raise ValueError(
                    "v3.0 format not enabled. Set FUZZER_BRIDGE_V3=true to enable."
                )
            if self.blocks is None:
                raise ValueError("v3.0 format requires 'blocks' field")
            if self.transactions is not None:
                raise ValueError("v3.0 format cannot have 'transactions' field")
            if self.env is not None:
                raise ValueError("v3.0 format cannot have 'env' field")

        return self
