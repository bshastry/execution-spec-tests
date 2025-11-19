"""
Converter module for transforming fuzzer DTOs to EEST domain models.

.. deprecated:: 1.0
   The direct converter functions are deprecated in favor of the processor
   architecture. Use `processors.v2_processor.V2Processor` for v2.0 inputs
   and `processors.v3_processor.V3Processor` for v3.0 inputs.

   The converter module will be maintained for backward compatibility but
   is no longer the recommended approach for new code.

This module performs explicit transformation from fuzzer's
JSON-RPC format (captured in DTOs) to EEST's internal domain
models (Transaction, Account, etc.).

Key Responsibilities:
1. Field mapping (gas → gas_limit, from → sender, etc.)
2. Creating EOA objects from private keys
3. Building proper EEST domain models with all required context
4. Preventing TestAddress pollution by setting sender
   BEFORE model_post_init

Migration Guide:
   Old approach::

       from fuzzer_bridge.converter import blockchain_test_from_fuzzer
       test = blockchain_test_from_fuzzer(fuzzer_data, fork, num_blocks=2)

   New approach::

       from fuzzer_bridge.processors.factory import ProcessorFactory
       from fuzzer_bridge.version_detector import detect_version

       version = detect_version(fuzzer_output)
       processor = ProcessorFactory.create_processor(version)
       result = processor.process(fuzzer_output, t8n=t8n, fork=fork)
"""

from typing import Dict, List

from ethereum_test_base_types import Address, Hash, HexNumber
from ethereum_test_exceptions import BlockException, TransactionException
from ethereum_test_forks import Fork
from ethereum_test_specs import BlockchainTest
from ethereum_test_tools import Account, AuthorizationTuple, Block, Transaction
from ethereum_test_types import Alloc, Environment
from ethereum_test_types.account_types import EOA

from .models import (
    FuzzerAccountInput,
    FuzzerAuthorizationInput,
    FuzzerGenesisInput,
    FuzzerOutput,
    FuzzerTransactionInput,
    InvalidBlockInput,
    ValidBlockInput,
)


def _is_transaction_level_exception(exception: BlockException | TransactionException) -> bool:
    """
    Determine if exception is transaction-level (causes state contamination).

    Transaction-level exceptions occur during transaction execution and can cause
    partial state updates (e.g., txs 0-11 succeed, tx 12 fails). To prevent state
    contamination, blocks with these exceptions should have empty transaction lists.

    Block-level exceptions occur during header validation and require transactions
    to be present for proper validation.

    Returns:
        True if exception is transaction-level (should create empty block)
        False if exception is block-level or RLP-level (preserve transactions)
    """
    # All BlockException are block-level
    if isinstance(exception, BlockException):
        return False

    # TransactionException: categorize by type
    if isinstance(exception, TransactionException):
        # RLP exceptions don't cause state contamination (pre-execution parsing errors)
        RLP_EXCEPTIONS = {
            TransactionException.RLP_ERROR_EOF,
            TransactionException.RLP_ERROR_SIZE,
            TransactionException.RLP_ERROR_SIZE_LEADING_ZEROS,
            TransactionException.RLP_INVALID_ACCESS_LIST_ADDRESS_TOO_LONG,
            TransactionException.RLP_INVALID_ACCESS_LIST_ADDRESS_TOO_SHORT,
            TransactionException.RLP_INVALID_ACCESS_LIST_STORAGE_TOO_LONG,
            TransactionException.RLP_INVALID_ACCESS_LIST_STORAGE_TOO_SHORT,
            TransactionException.RLP_INVALID_DATA,
            TransactionException.RLP_INVALID_GASLIMIT,
            TransactionException.RLP_INVALID_HEADER,
            TransactionException.RLP_INVALID_NONCE,
            TransactionException.RLP_INVALID_SIGNATURE_R,
            TransactionException.RLP_INVALID_SIGNATURE_S,
            TransactionException.RLP_INVALID_TO,
            TransactionException.RLP_INVALID_VALUE,
            TransactionException.RLP_LEADING_ZEROS_BASEFEE,
            TransactionException.RLP_LEADING_ZEROS_DATA_SIZE,
            TransactionException.RLP_LEADING_ZEROS_GASLIMIT,
            TransactionException.RLP_LEADING_ZEROS_GASPRICE,
            TransactionException.RLP_LEADING_ZEROS_NONCE,
            TransactionException.RLP_LEADING_ZEROS_NONCE_SIZE,
            TransactionException.RLP_LEADING_ZEROS_PRIORITY_FEE,
            TransactionException.RLP_LEADING_ZEROS_R,
            TransactionException.RLP_LEADING_ZEROS_S,
            TransactionException.RLP_LEADING_ZEROS_V,
            TransactionException.RLP_LEADING_ZEROS_VALUE,
            TransactionException.RLP_TOO_FEW_ELEMENTS,
            TransactionException.RLP_TOO_MANY_ELEMENTS,
        }

        # Transaction-level exceptions (execution-time, can contaminate state)
        return exception not in RLP_EXCEPTIONS

    return False


def parse_exception_string(
    exception_str: str | List[str],
) -> BlockException | TransactionException | List[BlockException | TransactionException]:
    """
    Parse exception string(s) from fuzzer format to EEST exception type(s).

    Supports:
    - Single: "BlockException.INVALID_STATE_ROOT"
    - Pipe-separated: "BlockException.INVALID_STATE_ROOT|BlockException.UNKNOWN_PARENT"
    - List: ["BlockException.INVALID_STATE_ROOT", "BlockException.UNKNOWN_PARENT"]

    Args:
        exception_str: Exception string(s) in fuzzer format, e.g.:
                      - "BlockException.INVALID_STATE_ROOT"
                      - "TransactionException.NONCE_TOO_LOW"
                      - "INVALID_TIMESTAMP" (legacy format)
                      - "BlockException.INVALID_STATE_ROOT|BlockException.UNKNOWN_PARENT" (multiple)
                      - ["BlockException.INVALID_STATE_ROOT", "BlockException.UNKNOWN_PARENT"] (list)

    Returns:
        Single exception or list of exceptions (depending on input)

    Raises:
        ValueError: If exception string cannot be parsed

    """
    # Handle list input
    if isinstance(exception_str, list):
        if len(exception_str) == 1:
            return parse_exception_string(exception_str[0])
        return [parse_exception_string(exc) for exc in exception_str]

    # Handle pipe-separated string
    if "|" in exception_str:
        exceptions = exception_str.split("|")
        if len(exceptions) == 1:
            return parse_exception_string(exceptions[0])
        return [parse_exception_string(exc.strip()) for exc in exceptions]

    # Single exception parsing - original logic
    # Split on dot to check if it has prefix
    parts = exception_str.split(".")

    if len(parts) == 2:
        # Format: "BlockException.VALUE" or "TransactionException.VALUE"
        prefix, value = parts

        if prefix == "BlockException":
            try:
                return BlockException[value]
            except KeyError:
                raise ValueError(f"Unknown BlockException value: {value}")
        elif prefix == "TransactionException":
            try:
                return TransactionException[value]
            except KeyError:
                raise ValueError(f"Unknown TransactionException value: {value}")
        else:
            raise ValueError(f"Unknown exception prefix: {prefix}")

    elif len(parts) == 1:
        # Legacy format: "VALUE" - try both exception types
        value = parts[0]

        # Try BlockException first
        try:
            return BlockException[value]
        except KeyError:
            pass

        # Try TransactionException
        try:
            return TransactionException[value]
        except KeyError:
            raise ValueError(
                f"Unknown exception value '{value}' (not found in BlockException or TransactionException)"
            )
    else:
        raise ValueError(f"Invalid exception format: {exception_str}")


def fuzzer_account_to_eest_account(fuzzer_account: FuzzerAccountInput) -> Account:
    """
    Convert fuzzer account DTO to EEST Account domain model.

    Args:
        fuzzer_account: Raw account data from fuzzer

    Returns:
        EEST Account ready for pre-state

    """
    return Account(
        balance=fuzzer_account.balance,
        nonce=fuzzer_account.nonce,
        code=fuzzer_account.code,
        storage=fuzzer_account.storage,
    )


def fuzzer_authorization_to_eest(
    fuzzer_auth: FuzzerAuthorizationInput,
) -> AuthorizationTuple:
    """
    Convert fuzzer authorization DTO to EEST AuthorizationTuple.

    Args:
        fuzzer_auth: Raw authorization data from fuzzer

    Returns:
        EEST AuthorizationTuple for EIP-7702 transactions

    """
    return AuthorizationTuple(
        chain_id=fuzzer_auth.chain_id,
        address=fuzzer_auth.address,
        nonce=fuzzer_auth.nonce,
        v=fuzzer_auth.v,
        r=fuzzer_auth.r,
        s=fuzzer_auth.s,
    )


def fuzzer_transaction_to_eest_transaction(
    fuzzer_tx: FuzzerTransactionInput,
    sender_eoa: EOA,
) -> Transaction:
    """
    Convert fuzzer transaction DTO to EEST Transaction domain model.

    This function performs explicit field mapping and MUST set sender BEFORE
    calling Transaction constructor to prevent TestAddress injection.

    Key Mappings:
    - fuzzer_tx.gas → transaction.gas_limit (JSON-RPC → EEST naming)
    - fuzzer_tx.from_ → sender_eoa (Address → EOA with private key)
    - fuzzer_tx.data → transaction.data (same field, explicit for clarity)

    Args:
        fuzzer_tx: Raw transaction data from fuzzer
        sender_eoa: EOA object created from private key (prevents TestAddress)

    Returns:
        EEST Transaction ready for block generation

    """
    # Build authorization list if present
    auth_list = None
    if fuzzer_tx.authorization_list:
        auth_list = [fuzzer_authorization_to_eest(auth) for auth in fuzzer_tx.authorization_list]

    # Create Transaction with sender set BEFORE model_post_init runs
    # This prevents Transaction.model_post_init from injecting TestAddress
    return Transaction(
        sender=sender_eoa,  # ✓ Set explicitly to prevent TestAddress
        to=fuzzer_tx.to,
        gas_limit=fuzzer_tx.gas,  # ✓ Explicit mapping: gas → gas_limit
        gas_price=fuzzer_tx.gas_price,
        max_fee_per_gas=fuzzer_tx.max_fee_per_gas,
        max_priority_fee_per_gas=fuzzer_tx.max_priority_fee_per_gas,
        nonce=fuzzer_tx.nonce,
        data=fuzzer_tx.data,
        value=fuzzer_tx.value,
        access_list=fuzzer_tx.access_list,
        blob_versioned_hashes=fuzzer_tx.blob_versioned_hashes,
        max_fee_per_blob_gas=fuzzer_tx.max_fee_per_blob_gas,
        authorization_list=auth_list,
    )


def create_sender_eoa_map(accounts: Dict[Address, FuzzerAccountInput]) -> Dict[Address, EOA]:
    """
    Create map of addresses to EOA objects from accounts with private keys.

    Args:
        accounts: Dictionary of address to fuzzer account data

    Returns:
        Dictionary mapping addresses to EOA objects for transaction signing

    Raises:
        AssertionError: If private key doesn't match the account address

    """
    senders: Dict[Address, EOA] = {}

    for addr, account in accounts.items():
        if account.private_key is None:
            continue

        # Create EOA from private key
        sender = EOA(key=account.private_key)

        # Verify private key matches address (safety check)
        assert Address(sender) == addr, (
            f"Private key for account {addr} does not match derived address {sender}"
        )

        senders[addr] = sender

    return senders


def blockchain_test_from_fuzzer_v2(
    fuzzer_output: FuzzerOutput,
    fork: Fork,
    num_blocks: int = 1,
    block_strategy: str = "distribute",
    block_time: int = 12,
) -> BlockchainTest:
    """
    Convert v2.0 fuzzer output to BlockchainTest instance.

    This is the v2.0 converter that generates blocks from a flat list of transactions.
    It orchestrates:
    1. Parsing and validation (already done by FuzzerOutput DTO)
    2. Creating EOA objects from private keys
    3. Converting DTOs to domain models
    4. Building blocks and test structure

    Args:
        fuzzer_output: Parsed and validated v2.0 fuzzer output (DTO)
        fork: Fork to use for the test
        num_blocks: Number of blocks to generate
        block_strategy: How to distribute transactions across blocks
                       - "distribute": Split evenly maintaining
                         nonce order
                       - "first-block": All transactions in first
                         block
        block_time: Seconds between block timestamps

    Returns:
        BlockchainTest instance ready for fixture generation

    Raises:
        AssertionError: If invariants are violated
                       (sender validation, etc.)

    """
    # Step 1: Convert accounts to EEST Account domain models
    pre_dict: Dict[Address, Account | None] = {}
    for addr, fuzzer_account in fuzzer_output.accounts.items():
        pre_dict[addr] = fuzzer_account_to_eest_account(fuzzer_account)
    pre = Alloc(pre_dict)

    # Step 2: Create EOA map for transaction signing
    sender_eoa_map = create_sender_eoa_map(fuzzer_output.accounts)

    # Step 3: Convert transactions to EEST Transaction domain models
    eest_transactions: list[Transaction] = []
    for fuzzer_tx in fuzzer_output.transactions:
        # Verify sender has private key
        assert fuzzer_tx.from_ in sender_eoa_map, (
            f"Sender {fuzzer_tx.from_} not found in accounts with private keys"
        )

        # Convert with explicit sender (prevents TestAddress injection)
        eest_tx = fuzzer_transaction_to_eest_transaction(
            fuzzer_tx,
            sender_eoa=sender_eoa_map[fuzzer_tx.from_],
        )
        eest_transactions.append(eest_tx)

    # Step 4: Build genesis environment
    env = fuzzer_output.env
    genesis_env = Environment(
        fee_recipient=env.fee_recipient,
        difficulty=0,  # Post-merge
        gas_limit=int(env.gas_limit),
        number=0,
        timestamp=HexNumber(int(env.timestamp) - 12),
        prev_randao=env.prev_randao or Hash(0),
        base_fee_per_gas=env.base_fee_per_gas if env.base_fee_per_gas else None,
        excess_blob_gas=env.excess_blob_gas if env.excess_blob_gas else None,
        blob_gas_used=env.blob_gas_used if env.blob_gas_used else None,
    ).set_fork_requirements(fork)

    # Step 5: Distribute transactions across blocks
    blocks = _distribute_transactions_to_blocks(
        eest_transactions,
        num_blocks,
        block_strategy,
        block_time,
        env,
        fuzzer_output.parent_beacon_block_root,
    )

    return BlockchainTest(
        pre=pre,
        blocks=blocks,
        post={},  # Post-state verification can be added later
        genesis_environment=genesis_env,
        chain_id=fuzzer_output.chain_id,
    )


def _distribute_transactions_to_blocks(
    transactions: list[Transaction],
    num_blocks: int,
    strategy: str,
    block_time: int,
    base_env: Environment,
    parent_beacon_block_root: Hash | None,
) -> list[Block]:
    """
    Distribute transactions across multiple blocks.

    Args:
        transactions: List of EEST Transaction objects (ready for execution)
        num_blocks: Number of blocks to create
        strategy: Distribution strategy ("distribute" or "first-block")
        block_time: Seconds between blocks
        base_env: Base environment for first block
        parent_beacon_block_root: Beacon root (only for first block)

    Returns:
        List of Block objects

    """
    if strategy == "first-block":
        # All transactions in first block, rest empty
        tx_distribution = [transactions] + [[] for _ in range(num_blocks - 1)]
    elif strategy == "distribute":
        # Split transactions evenly maintaining nonce order
        if not transactions:
            tx_distribution = [[] for _ in range(num_blocks)]
        else:
            result = []
            chunk_size = len(transactions) // num_blocks
            remainder = len(transactions) % num_blocks

            start = 0
            for i in range(num_blocks):
                # Distribute remainder across first blocks
                current_chunk_size = chunk_size + (1 if i < remainder else 0)
                end = start + current_chunk_size
                result.append(transactions[start:end])
                start = end

            tx_distribution = result
    else:
        raise ValueError(f"Unknown block strategy: {strategy}")

    # Create blocks with incrementing timestamps
    base_timestamp = int(base_env.timestamp)
    blocks = []
    for i, block_txs in enumerate(tx_distribution):
        blocks.append(
            Block(
                txs=block_txs,
                timestamp=base_timestamp + (i * block_time),
                fee_recipient=base_env.fee_recipient,
                parent_beacon_block_root=parent_beacon_block_root if i == 0 else None,
            )
        )

    return blocks


def blockchain_test_from_fuzzer(
    fuzzer_output: FuzzerOutput,
    fork: Fork,
    num_blocks: int = 1,
    block_strategy: str = "distribute",
    block_time: int = 12,
) -> BlockchainTest:
    """
    Convert fuzzer output to BlockchainTest (version-aware routing).

    .. deprecated:: 1.0
       Use the processor architecture instead:
       `processors.factory.ProcessorFactory.create_processor(version)`

    This function automatically routes to the correct converter based on the
    version field in the fuzzer output:
    - v2.0: Routes to blockchain_test_from_fuzzer_v2 (transaction distribution)
    - v3.0: Routes to blockchain_test_from_fuzzer_v3 (explicit blocks)

    Args:
        fuzzer_output: Parsed and validated fuzzer output
        fork: Fork to use for the test
        num_blocks: Number of blocks to generate (v2.0 only)
        block_strategy: Transaction distribution strategy (v2.0 only)
        block_time: Seconds between blocks (v2.0 only)

    Returns:
        BlockchainTest instance ready for fixture generation

    Raises:
        ValueError: If fuzzer version is unsupported

    """
    import warnings

    # Emit deprecation warning
    warnings.warn(
        "blockchain_test_from_fuzzer() is deprecated. "
        "Use processors.factory.ProcessorFactory instead. "
        "See PROCESSOR_ARCHITECTURE.md for migration guide.",
        DeprecationWarning,
        stacklevel=2,
    )

    if fuzzer_output.version == "2.0":
        return blockchain_test_from_fuzzer_v2(
            fuzzer_output,
            fork,
            num_blocks=num_blocks,
            block_strategy=block_strategy,
            block_time=block_time,
        )
    elif fuzzer_output.version == "3.0":
        # Warn if v2.0-specific parameters are provided
        if num_blocks != 1 or block_strategy != "distribute" or block_time != 12:
            warnings.warn(
                "v3.0 format ignores num_blocks, block_strategy, and block_time "
                "(blocks are explicitly defined in input)",
                UserWarning,
                stacklevel=2,
            )
        return blockchain_test_from_fuzzer_v3(fuzzer_output, fork)
    else:
        raise ValueError(
            f"Unsupported fuzzer version: {fuzzer_output.version}. Supported versions: 2.0, 3.0"
        )


def _validate_withdrawal_indices(blocks: list) -> None:
    """
    Validate withdrawal indices are sequential across blocks.

    From validation report Section 5.2: withdrawal indices must be
    sequential spanning the entire sequence of withdrawals.

    Note: Invalid blocks are skipped as they don't have withdrawals field.
    """
    expected_next = 0
    for block_num, block in enumerate(blocks):
        # Skip invalid blocks (they don't have withdrawals)
        if isinstance(block, InvalidBlockInput):
            continue

        # Only ValidBlockInput has withdrawals field
        if block.withdrawals is None:
            continue
        for w in block.withdrawals:
            if int(w.index) != expected_next:
                raise ValueError(
                    f"Block {block_num}: withdrawal index {w.index} expected {hex(expected_next)}"
                )
            expected_next += 1


def _build_genesis_from_v3(
    genesis: FuzzerGenesisInput,
    fork: Fork,
) -> Environment:
    """
    Build genesis environment from explicit v3.0 genesis field.

    Args:
        genesis: Genesis parameters from v3.0 format
        fork: Fork to use

    Returns:
        Genesis environment (block 0)
    """
    return Environment(
        fee_recipient=Address("0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"),
        difficulty=0,
        gas_limit=int(genesis.gas_limit),
        number=0,
        timestamp=int(genesis.timestamp),
        prev_randao=Hash(0),
    ).set_fork_requirements(fork)


def _convert_block_v3(
    fuzzer_block: ValidBlockInput | InvalidBlockInput,
    sender_eoa_map: Dict[Address, EOA],
) -> Block:
    """
    Convert a single v3.0 block to EEST Block.

    Handles both valid and invalid blocks:
    - ValidBlockInput: Full conversion with transactions and environment
    - InvalidBlockInput: Minimal conversion with just exception field

    Args:
        fuzzer_block: Block data from v3.0 format (valid or invalid)
        sender_eoa_map: Map of addresses to EOA for signing

    Returns:
        EEST Block instance

    """
    # Check if this is an invalid block
    if isinstance(fuzzer_block, InvalidBlockInput):
        # Invalid block: parse exception first
        exception = parse_exception_string(fuzzer_block.expect_exception)

        # ALL invalid blocks with structured format should use empty transaction lists.
        # Reason: Goevmlab creates invalid blocks by either:
        # 1. Transaction-level exceptions: Injecting invalid transactions (e.g., duplicate nonce)
        #    → Causes partial state contamination when some txs succeed before one fails
        # 2. Block-level exceptions: Mutating header fields (e.g., baseFee, gasLimit, timestamp)
        #    → Makes transactions unexecutable with mutated parameters
        #
        # In both cases, attempting to execute transactions through t8n causes failures.
        # Empty blocks allow proper invalid block testing without execution issues.
        if fuzzer_block.block is not None:
            return Block(
                number=fuzzer_block.block.number,
                timestamp=fuzzer_block.block.timestamp,
                gas_limit=fuzzer_block.block.gas_limit,
                coinbase=fuzzer_block.block.coinbase,
                base_fee_per_gas=fuzzer_block.block.base_fee_per_gas,
                difficulty=fuzzer_block.block.difficulty,
                mix_hash=fuzzer_block.block.mix_hash,
                excess_blob_gas=fuzzer_block.block.excess_blob_gas,
                blob_gas_used=fuzzer_block.block.blob_gas_used,
                parent_beacon_block_root=fuzzer_block.block.parent_beacon_block_root,
                extra_data=fuzzer_block.block.extra_data,
                txs=[],  # CRITICAL: Empty transactions to prevent execution issues
                exception=exception,
                skip_exception_verification=True,
            )

        # RLP-only format (legacy): minimal conversion without transaction execution
        # Note: RLP will be handled during fixture generation
        return Block(
            number=fuzzer_block.number,
            exception=exception,
        )

    # Valid block: full conversion (existing logic)
    assert isinstance(fuzzer_block, ValidBlockInput), f"Unexpected block type: {type(fuzzer_block)}"

    # Convert transactions
    eest_txs = []
    for fuzzer_tx in fuzzer_block.transactions:
        if fuzzer_tx.from_ not in sender_eoa_map:
            raise ValueError(f"Sender {fuzzer_tx.from_} not found in accounts with private keys")

        eest_tx = fuzzer_transaction_to_eest_transaction(
            fuzzer_tx,
            sender_eoa=sender_eoa_map[fuzzer_tx.from_],
        )
        eest_txs.append(eest_tx)

    # Convert withdrawals if present
    eest_withdrawals = None
    if fuzzer_block.withdrawals is not None:
        from ethereum_test_tools import Withdrawal

        eest_withdrawals = [
            Withdrawal(
                index=w.index,
                validator_index=w.validator_index,
                address=w.address,
                amount=w.amount,
            )
            for w in fuzzer_block.withdrawals
        ]

    # Create Block with fuzzer-specified environment
    return Block(
        txs=eest_txs,
        timestamp=fuzzer_block.timestamp,
        number=fuzzer_block.number,
        gas_limit=fuzzer_block.gas_limit,
        fee_recipient=fuzzer_block.coinbase,
        base_fee_per_gas=fuzzer_block.base_fee_per_gas,
        difficulty=fuzzer_block.difficulty,
        prev_randao=fuzzer_block.mix_hash,
        excess_blob_gas=fuzzer_block.excess_blob_gas,
        blob_gas_used=fuzzer_block.blob_gas_used,
        parent_beacon_block_root=fuzzer_block.parent_beacon_block_root,
        withdrawals=eest_withdrawals,
        extra_data=fuzzer_block.extra_data,
    )


def blockchain_test_from_fuzzer_v3(
    fuzzer_output: FuzzerOutput,
    fork: Fork,
) -> BlockchainTest:
    """
    Convert v3.0 fuzzer output to BlockchainTest.

    This is the main entry point for v3.0 conversion.

    Key differences from v2.0:
    - Blocks are explicitly specified (not generated)
    - Per-block environments instead of single global env
    - Withdrawals supported (EIP-4895)
    - Per-block beacon roots (EIP-4788)

    Args:
        fuzzer_output: Parsed v3.0 fuzzer output (has 'blocks' field)
        fork: Fork to use for the test

    Returns:
        BlockchainTest instance

    Raises:
        ValueError: If fuzzer_output is not v3.0 format or validation fails

    """
    if fuzzer_output.version != "3.0":
        raise ValueError(f"Expected v3.0 format, got {fuzzer_output.version}")

    if fuzzer_output.blocks is None or len(fuzzer_output.blocks) == 0:
        raise ValueError("v3.0 format must have at least one block")

    # Step 1: Validate withdrawal indices (Section 5.2)
    _validate_withdrawal_indices(fuzzer_output.blocks)

    # Step 2: Convert accounts (same as v2.0)
    pre_dict: Dict[Address, Account | None] = {}
    for addr, fuzzer_account in fuzzer_output.accounts.items():
        pre_dict[addr] = fuzzer_account_to_eest_account(fuzzer_account)
    pre = Alloc(pre_dict)

    # Step 3: Create EOA map (same as v2.0)
    sender_eoa_map = create_sender_eoa_map(fuzzer_output.accounts)

    # Step 4: Convert each block
    blocks = []
    for fuzzer_block in fuzzer_output.blocks:
        block = _convert_block_v3(fuzzer_block, sender_eoa_map)
        blocks.append(block)

    # Step 5: Build genesis from explicit genesis field
    genesis_env = _build_genesis_from_v3(fuzzer_output.genesis, fork)

    # Step 6: Build BlockchainTest
    return BlockchainTest(
        pre=pre,
        blocks=blocks,
        post={},  # Post-state verification can be added later
        genesis_environment=genesis_env,
        chain_id=fuzzer_output.chain_id,
    )
