# Next Session: Fuzzer Bridge Processor Architecture - Phases 7-10

## Session Context & Objective

**Goal**: Complete the remaining phases (7-10) of the processor-based architecture for fuzzer bridge v2/v3 segregation.

**Status**: Core architecture (Phases 0-6) is complete and tested. Now need CLI integration, parallel processing updates, migration validation, and documentation.

---

## 🎯 Quick Summary of What's Done

### ✅ Completed (Phases 0-6)

**13 atomic commits** implementing:

1. **Phase 0**: Feature flag infrastructure
   - Config flag: `use_version_processors` (default: `False`)
   - Enable via: `FUZZER_USE_PROCESSORS=true`

2. **Phase 1**: Version detection layer
   - `detect_version(data)`: Detect from dict
   - `detect_from_file(path)`: Detect from file
   - File: [src/cli/fuzzer_bridge/version_detector.py](src/cli/fuzzer_bridge/version_detector.py)

3. **Phase 2**: Processor base infrastructure
   - Abstract base class: `FuzzerProcessor`
   - Methods: `get_cli_params()`, `process()`, `validate_params()`
   - File: [src/cli/fuzzer_bridge/processors/base.py](src/cli/fuzzer_bridge/processors/base.py)

4. **Phase 3**: V2 Processor
   - Parameters: `num_blocks`, `block_strategy`, `block_time`, `random_blocks`
   - File: [src/cli/fuzzer_bridge/processors/v2_processor.py](src/cli/fuzzer_bridge/processors/v2_processor.py)

5. **Phase 4**: V3 Processor
   - No block params (explicit blocks in input)
   - Warns if v2 params provided
   - File: [src/cli/fuzzer_bridge/processors/v3_processor.py](src/cli/fuzzer_bridge/processors/v3_processor.py)

6. **Phase 5**: Processor factory
   - Registry: `{"2.0": V2Processor, "3.0": V3Processor}`
   - File: [src/cli/fuzzer_bridge/processors/factory.py](src/cli/fuzzer_bridge/processors/factory.py)

7. **Phase 6**: BlocktestBuilder integration
   - Feature flag routing in `build_blocktest()`
   - File: [src/cli/fuzzer_bridge/blocktest_builder.py](src/cli/fuzzer_bridge/blocktest_builder.py:43-106)

**Test Coverage**:
- ✅ 32 passing processor tests
- ✅ 29 existing fuzzer_bridge tests pass (no regressions)
- ✅ 100% backward compatibility

**Reference**: [PROCESSOR_ARCHITECTURE_IMPLEMENTATION.md](PROCESSOR_ARCHITECTURE_IMPLEMENTATION.md)

---

## 🚀 What Needs to Be Done (Phases 7-10)

### Phase 7: CLI Integration (Priority: HIGH)

**Objective**: Add early version detection to CLI with user-friendly warnings

**Location**: [src/cli/fuzzer_bridge/cli.py](src/cli/fuzzer_bridge/cli.py)

#### Key Requirements:

1. **Early Version Detection in Single File Processing**
   - Function: `process_single_file()` (line 39)
   - Add version detection before loading JSON
   - Log detected version when not quiet
   - Warn if v2 params used with v3 input

2. **Early Version Detection in Parallel Workers**
   - Function: `process_single_file_worker()` (line 91)
   - Same logic as single file but for workers
   - Ensure proper error handling

3. **User-Facing Warnings**
   ```python
   # If v3 detected and v2 params provided:
   click.echo(
       f"Warning: v3.0 format ignores v2 parameters: {used_v2_params}",
       err=True
   )
   ```

#### Implementation Steps (TDD):

1. **Commit 7.1**: Test CLI version detection
   - File: `src/cli/tests/test_cli_version_aware.py`
   - Test early detection before processing
   - Test warnings for mismatched params
   - Test quiet mode suppresses messages

2. **Commit 7.2**: Add version detection to `process_single_file()`
   - Import: `from .version_detector import detect_from_file`
   - Detect early (before JSON load)
   - Log version if not quiet
   - Warn on v2 params with v3

3. **Commit 7.3**: Add version detection to `process_single_file_worker()`
   - Same logic as single file
   - Test with parallel processing

#### Key Code Location:
```python
# src/cli/fuzzer_bridge/cli.py:39-88
def process_single_file(
    input_file: Path,
    output_path: Path,
    builder: BlocktestBuilder,
    fork: Optional[str],
    pretty: bool,
    quiet: bool,
    num_blocks: int = 1,
    block_strategy: str = "distribute",
    block_time: int = 12,
    random_blocks: bool = False,
) -> Dict[str, Any]:
    # ADD VERSION DETECTION HERE
    pass
```

---

### Phase 8: Parallel Processing Update (Priority: HIGH)

**Objective**: Ensure parallel workers properly use processor architecture

**Location**: [src/cli/fuzzer_bridge/cli.py:91-146](src/cli/fuzzer_bridge/cli.py#L91-L146)

#### Key Requirements:

1. **Worker Function Updates**
   - Function: `process_single_file_worker()` (line 91)
   - Already creates builder per worker (line 107)
   - Just needs version detection integration from Phase 7

2. **Batch Processing**
   - Function: `process_file_batch()` (line 149)
   - Should already work via worker updates
   - Verify no additional changes needed

#### Implementation Steps (TDD):

1. **Commit 8.1**: Test parallel worker with processors
   - File: `src/cli/tests/test_cli_parallel_processors.py`
   - Test worker processes v2 with processors enabled
   - Test worker processes v3 with processors enabled
   - Test feature flag controls routing

2. **Commit 8.2**: Update worker implementation
   - Integrate version detection (from Phase 7)
   - Test with actual parallel execution
   - Verify no race conditions

#### Testing Strategy:
```python
# Test with both flags
@pytest.mark.parametrize("use_processors", [False, True])
def test_parallel_worker_with_feature_flag(use_processors):
    # Set flag, run worker, verify correct path used
    pass
```

---

### Phase 9: Migration & Performance Testing (Priority: MEDIUM)

**Objective**: Validate equivalence between old and new paths, ensure no performance regression

#### Key Requirements:

1. **Migration Compatibility Tests**
   - Test old path vs new path produce identical output
   - Use multiple test vectors (v2 minimal, v2 complex, v3 simple, v3 complex)
   - Deep equality check of fixtures

2. **Performance Benchmarks**
   - Test processing time for large datasets
   - Ensure processor overhead < 10%
   - Test parallel processing performance

#### Implementation Steps (TDD):

1. **Commit 9.1**: Add migration equivalence tests
   - File: `src/cli/tests/test_migration_equivalence.py`
   - Test v2 minimal: old == new
   - Test v2 complex (1000 txs): old == new
   - Test v3: new path only

2. **Commit 9.2**: Add performance benchmarks
   - File: `src/cli/tests/test_processor_performance.py`
   - Benchmark v2 processing (old vs new)
   - Benchmark v3 processing (new only)
   - Benchmark parallel processing

3. **Commit 9.3**: Production validation tests
   - Test with real fuzzer output samples
   - Test large batch processing
   - Test error handling and recovery

#### Test Implementation:
```python
def test_old_and_new_produce_identical_output():
    """Critical: Verify no behavior change."""
    v2_data = load_test_vector("v2_complex.json")

    # Old path
    with patch("config.use_version_processors", False):
        old_result = build_blocktest(v2_data)

    # New path
    with patch("config.use_version_processors", True):
        new_result = build_blocktest(v2_data)

    # Deep equality
    assert old_result == new_result
```

---

### Phase 10: Documentation & Rollout (Priority: MEDIUM)

**Objective**: Document architecture, add deprecation warnings, plan gradual rollout

#### Key Requirements:

1. **Processor Architecture Documentation**
   - How to add new versions
   - Design decisions and rationale
   - Testing strategy
   - Migration guide

2. **Deprecation Warnings**
   - Warn when using old converter path directly
   - Guide users to enable processors
   - Timeline for default flip

3. **Gradual Rollout Plan**
   - When to enable by default
   - Communication strategy
   - Rollback plan

#### Implementation Steps:

1. **Commit 10.1**: Add processor README
   - File: `src/cli/fuzzer_bridge/processors/README.md`
   - Architecture diagram
   - How to add new versions
   - Testing requirements

2. **Commit 10.2**: Add deprecation warnings
   - File: `src/cli/fuzzer_bridge/converter.py`
   - Warn on direct `blockchain_test_from_fuzzer()` usage
   - Suggest enabling processors

3. **Commit 10.3**: Update main README
   - File: `src/cli/fuzzer_bridge/README.md`
   - Document processor architecture
   - Show migration examples
   - Document feature flags

4. **Commit 10.4**: Create rollout plan
   - File: `PROCESSOR_ROLLOUT_PLAN.md`
   - Phased rollout timeline
   - Success criteria
   - Rollback procedures

---

## 📁 Key Files Reference

### Production Code
```
src/cli/fuzzer_bridge/
├── config.py                         # Feature flags (DONE)
├── version_detector.py               # Version detection (DONE)
├── blocktest_builder.py:43-106       # Integration point (DONE)
├── cli.py:39-88                      # Need Phase 7: process_single_file()
├── cli.py:91-146                     # Need Phase 8: parallel workers
├── converter.py:311-364              # Need Phase 10: deprecation
├── processors/
│   ├── base.py                       # Abstract base (DONE)
│   ├── v2_processor.py               # V2 implementation (DONE)
│   ├── v3_processor.py               # V3 implementation (DONE)
│   └── factory.py                    # Factory (DONE)
```

### Test Files
```
src/cli/tests/
├── test_config.py                    # Config tests (DONE)
├── test_version_detector.py          # Detection tests (DONE)
├── test_processor_*.py               # Processor tests (DONE)
├── test_cli_version_aware.py         # Need Phase 7: CLI detection
├── test_cli_parallel_processors.py   # Need Phase 8: Parallel
├── test_migration_equivalence.py     # Need Phase 9: Migration
├── test_processor_performance.py     # Need Phase 9: Performance
```

### Documentation
```
PROCESSOR_ARCHITECTURE_IMPLEMENTATION.md  # What's done (EXISTS)
src/cli/fuzzer_bridge/processors/README.md  # Need Phase 10
PROCESSOR_ROLLOUT_PLAN.md                    # Need Phase 10
```

---

## 🧪 Testing Philosophy

**Follow TDD Cycle**:
1. Write test (Red)
2. Implement minimal code (Green)
3. Refactor if needed
4. Commit

**Test Coverage Requirements**:
- Every new function must have tests
- Every edge case must have a test
- All existing tests must pass

**Run Tests**:
```bash
# Phase 7-8 tests
uv run pytest src/cli/tests/test_cli*.py -v

# Migration tests
uv run pytest src/cli/tests/test_migration*.py -v

# Performance benchmarks
uv run pytest src/cli/tests/test_processor_performance.py -v

# Regression check (MUST PASS)
uv run pytest src/cli/tests/test_fuzzer_bridge.py -v
```

---

## 🔍 Implementation Guidelines

### CLI Integration (Phase 7)

**Pattern**:
```python
from .config import config
from .version_detector import detect_from_file

def process_single_file(...):
    # Early version detection (if processors enabled)
    if config.use_version_processors:
        version = detect_from_file(input_file)

        if not quiet:
            click.echo(f"Detected version: {version}", err=True)

        # Warn on mismatched params
        if version == "3.0":
            v2_params = [k for k in ["num_blocks", "block_strategy", "random_blocks"]
                         if k in kwargs and kwargs[k] is not None]
            if v2_params:
                click.echo(
                    f"Warning: v3.0 ignores v2 parameters: {v2_params}",
                    err=True
                )

    # Continue with existing processing
    with open(input_file) as f:
        fuzzer_data = json.load(f)
    # ...
```

### Migration Tests (Phase 9)

**Critical Test**:
```python
def test_backward_compatibility_v2():
    """Ensure new path produces identical output for v2."""
    test_vectors = [
        "fuzzer_test_0.json",  # Complex
        "fuzzer_test_1.json",
        "fuzzer_test_2.json",
    ]

    for vector in test_vectors:
        v2_data = load_vector(vector)

        # Process with both paths
        old_result = process_with_flag(v2_data, use_processors=False)
        new_result = process_with_flag(v2_data, use_processors=True)

        # Must be identical
        assert old_result == new_result, f"Mismatch in {vector}"
```

---

## 🎯 Success Criteria

**Phase 7 Complete When**:
- ✅ CLI detects version early (before full parsing)
- ✅ Warnings shown for mismatched v2/v3 params
- ✅ Both single-file and parallel workers updated
- ✅ All tests pass with processors enabled/disabled

**Phase 8 Complete When**:
- ✅ Parallel workers use processor architecture
- ✅ No race conditions or worker issues
- ✅ Performance equivalent to old path

**Phase 9 Complete When**:
- ✅ Migration tests prove equivalence (old == new for v2)
- ✅ Performance benchmarks show < 10% overhead
- ✅ Large dataset tests pass

**Phase 10 Complete When**:
- ✅ Processor architecture documented
- ✅ Deprecation warnings added
- ✅ Rollout plan created
- ✅ All tests green

---

## 🚨 Critical Reminders

1. **Backward Compatibility**: Every commit must pass existing tests
2. **Feature Flag**: Default is `False` until Phase 10 complete
3. **TDD Always**: Test before code, no exceptions
4. **Atomic Commits**: Each commit is functional and reversible
5. **Zero Regressions**: All 29 existing tests must pass

---

## 🏁 Recommended Session Flow

**Suggested Order**:

1. **Start with Phase 7** (CLI integration)
   - Highest impact, user-facing
   - Required for Phase 8

2. **Then Phase 8** (Parallel processing)
   - Builds on Phase 7
   - Critical for production usage

3. **Then Phase 9** (Migration/performance)
   - Validate no regressions
   - Build confidence for rollout

4. **Finally Phase 10** (Documentation/rollout)
   - Wrap up with docs
   - Plan for default enable

**Estimated Time**:
- Phase 7: 2-3 hours (5-6 commits)
- Phase 8: 1-2 hours (2-3 commits)
- Phase 9: 2-3 hours (4-5 commits)
- Phase 10: 1-2 hours (3-4 commits)
- **Total**: 6-10 hours

---

## 📚 Reference Commands

```bash
# Run phase-specific tests
uv run pytest src/cli/tests/test_cli*.py -v
uv run pytest src/cli/tests/test_migration*.py -v
uv run pytest src/cli/tests/test_processor_performance.py -v

# Run all processor tests
uv run pytest src/cli/tests/test_*processor*.py -v

# Regression check (MUST PASS)
uv run pytest src/cli/tests/test_fuzzer_bridge.py -v

# Run with processors enabled
FUZZER_USE_PROCESSORS=true uv run pytest src/cli/tests/ -v

# Run with v3 enabled
FUZZER_BRIDGE_V3=true uv run pytest src/cli/tests/ -v

# Run everything
FUZZER_BRIDGE_V3=true FUZZER_USE_PROCESSORS=true uv run pytest src/cli/tests/ -v
```

---

## 💡 Quick Start Next Session

**First Commands**:
```bash
# Check current status
git log --oneline --no-decorate | head -15
git status

# Review implementation summary
cat PROCESSOR_ARCHITECTURE_IMPLEMENTATION.md

# Start Phase 7
uv run pytest src/cli/tests/test_cli_version_aware.py -v  # Should fail (doesn't exist)
```

**Then**:
1. Create test file for CLI version detection
2. Write failing tests
3. Implement minimal CLI changes
4. Make tests pass
5. Commit
6. Repeat

---

## 📖 Architecture Recap

```
User Input (JSON file)
    ↓
detect_from_file(path)  ← Version detection (Phase 1)
    ↓
ProcessorFactory.create_processor(version)  ← Factory (Phase 5)
    ↓
processor.validate_params(kwargs)  ← Validation (Phase 2)
    ↓
processor.process(data, **kwargs)  ← Version-specific logic (Phases 3-4)
    ↓
BlockchainFixture (output)
```

**Feature Flag**:
- `use_version_processors=False`: Old path (converter)
- `use_version_processors=True`: New path (processors)

---

## 🎓 Key Learnings From Phases 0-6

1. **Feature flags enable safe rollout** - Critical for zero-risk migration
2. **Early detection saves parsing** - Detect version before full JSON parse
3. **Abstract base enforces consistency** - All processors follow same interface
4. **Factory pattern simplifies extension** - Add new versions easily
5. **TDD prevents regressions** - Every commit had tests first

---

## ✅ Ready to Start?

**You have everything needed**:
- ✅ Complete architecture (Phases 0-6)
- ✅ 32 passing tests (foundation solid)
- ✅ Clear roadmap (Phases 7-10)
- ✅ Detailed implementation guide
- ✅ Zero regressions to date

**Next action**: Start Phase 7 with CLI version detection test.

Good luck! 🚀
