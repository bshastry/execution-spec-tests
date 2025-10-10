# Fuzzer Bridge Processor Architecture

> **Status**: Production-ready (Phases 1-10 complete)
> **Version**: 1.0
> **Last Updated**: 2025-10-10

## Overview

The fuzzer bridge processor architecture provides a clean, scalable, and version-aware system for converting fuzzer-generated test vectors into Ethereum execution spec tests. This document describes the architecture, design decisions, and usage patterns.

## Architecture Goals

1. **Version Segregation**: Complete separation of v2.0 and v3.0 format handling
2. **Backward Compatibility**: Existing v2 workflows continue unchanged
3. **Type Safety**: Strong typing with Pydantic models throughout
4. **Testability**: Comprehensive test coverage with TDD approach
5. **Performance**: Minimal overhead (<25%) compared to legacy converter
6. **Extensibility**: Easy to add support for future versions (v4.0, etc.)

## Core Components

### 1. Version Detection (`version_detector.py`)

Early, fast version detection that examines JSON structure:

```python
from fuzzer_bridge.version_detector import detect_version

version = detect_version(fuzzer_output)  # Returns "2.0" or "3.0"
```

**Key Features:**
- Fast O(1) detection via version field lookup
- Validates version format (major.minor)
- Raises clear errors for unsupported versions

### 2. Processor Factory (`processors/factory.py`)

Central registry and factory for version-specific processors:

```python
from fuzzer_bridge.processors.factory import ProcessorFactory

processor = ProcessorFactory.create_processor("2.0")  # Returns V2Processor
processor = ProcessorFactory.create_processor("3.0")  # Returns V3Processor
```

**Key Features:**
- Singleton pattern for processor instances
- Runtime version registration
- Type-safe processor creation
- Clear error messages for unsupported versions

### 3. Base Processor (`processors/base.py`)

Abstract base class defining the processor interface:

```python
class BaseProcessor(ABC):
    @abstractmethod
    def process(
        self,
        fuzzer_output: Dict[str, Any],
        t8n: TransitionTool,
        fork: Fork,
        **kwargs
    ) -> Dict[str, Any]:
        """Process fuzzer output and return fixture."""
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> None:
        """Validate processor-specific parameters."""
        pass
```

### 4. V2 Processor (`processors/v2_processor.py`)

Handles v2.0 format (legacy fuzzer output):

```python
# Processes v2.0 format with all legacy parameters
result = v2_processor.process(
    fuzzer_output,
    t8n=t8n,
    fork=Prague,
    num_blocks=3,
    block_strategy="distribute",
    block_time=12
)
```

**Supported Parameters:**
- `num_blocks`: Number of blocks to distribute transactions across
- `block_strategy`: "distribute" or "first-block"
- `block_time`: Block timestamp increment (seconds)

### 5. V3 Processor (`processors/v3_processor.py`)

Handles v3.0 format (multi-block fuzzer output):

```python
# Processes v3.0 format (blocks pre-defined in input)
result = v3_processor.process(
    fuzzer_output,
    t8n=t8n,
    fork=Prague
)
# Note: num_blocks, block_strategy ignored (warns if provided)
```

**Key Differences:**
- Blocks are defined in fuzzer output, not generated
- Transactions pre-assigned to specific blocks
- Different genesis timestamp handling
- Stricter validation requirements

## Integration Points

### 1. BlocktestBuilder

The main entry point has version-aware routing:

```python
from fuzzer_bridge.blocktest_builder import BlocktestBuilder
from ethereum_clis import GethTransitionTool

t8n = GethTransitionTool()
builder = BlocktestBuilder(transition_tool=t8n)

# Automatic version detection and routing
result = builder.build_blocktest(fuzzer_output, num_blocks=2)
```

**Routing Logic:**
1. Check `config.use_version_processors` flag
2. If enabled: Detect version → Get processor → Process
3. If disabled: Use legacy converter (backward compatibility)

### 2. CLI (`cli.py`)

Command-line tools with version-aware processing:

```python
# Single file processing (auto-detects version)
process_single_file(
    input_path=Path("fuzzer_output.json"),
    output_path=Path("fixture.json"),
    builder=builder,
    fork="Prague",
    num_blocks=2
)

# Directory processing (handles mixed versions)
process_directory(
    input_dir=Path("fuzzer_outputs/"),
    output_dir=Path("fixtures/"),
    builder=builder,
    fork=None,  # Auto-detect from each file
    num_blocks=2
)
```

### 3. Parallel Processing (`cli.py`)

Optimized parallel processing with worker pools:

```python
process_directory_parallel(
    input_dir=Path("fuzzer_outputs/"),
    output_dir=Path("fixtures/"),
    builder=builder,
    fork=None,
    num_workers=4,  # Parallel workers
    num_blocks=2
)
```

**Features:**
- Worker pool for concurrent processing
- Per-file version detection
- Progress bars for batch operations
- Graceful error handling

## Configuration

### Environment Variables

```bash
# Enable processor architecture (default: false)
export FUZZER_USE_PROCESSORS=true

# Enable v3.0 format support (default: false)
export FUZZER_BRIDGE_V3=true

# Strict version validation (default: true)
export FUZZER_STRICT_VERSION=true
```

### Programmatic Configuration

```python
from fuzzer_bridge.config import config

# Check configuration
if config.use_version_processors:
    print("Processor architecture enabled")

if config.enable_v3_format:
    print("V3.0 format supported")
```

## Migration Guide

### Enabling Processors

**Phase 1: Testing**
```bash
# Run existing tests with processors enabled
FUZZER_USE_PROCESSORS=true pytest src/cli/tests/
```

**Phase 2: Validation**
```bash
# Compare old vs new output
python -m cli.fuzzer_bridge.validate_migration
```

**Phase 3: Production**
```bash
# Update configuration
export FUZZER_USE_PROCESSORS=true

# Run fuzzer bridge normally
python -m cli.fuzzer_bridge.main process input/ output/
```

### Backward Compatibility

The architecture is **fully backward compatible**:

- If `FUZZER_USE_PROCESSORS=false` (default), uses legacy converter
- All existing scripts continue to work unchanged
- Migration can be done incrementally per environment

## Performance Characteristics

Based on comprehensive benchmark tests:

| Metric | Legacy Path | Processor Path | Overhead |
|--------|-------------|----------------|----------|
| Simple v2 (17 txs) | 0.279s | 0.334s | +19.7% |
| Complex v2 (many txs) | 4.750s | 3.867s | -18.6% |
| V3 single block | N/A | 0.061s | N/A |
| V3 multi-block | N/A | 0.067s | N/A |

**Key Findings:**
- Overhead varies by input complexity (-18.6% to +19.7%)
- V3 processing is very fast (< 0.1s for typical cases)
- No performance degradation on sequential processing
- Scales linearly with block count

## Testing

### Test Suites

1. **Migration Equivalence** (`test_migration_equivalence.py`)
   - Validates new path produces identical output to legacy path
   - Tests all v2 parameter combinations
   - Validates v3 processor output structure

2. **Performance Benchmarks** (`test_processor_performance.py`)
   - Measures processing overhead
   - Validates scalability
   - Tests sequential processing consistency

3. **Production Validation** (`test_production_validation.py`)
   - Large batch processing
   - Mixed v2/v3 directories
   - Error recovery scenarios
   - High-volume continuous processing

### Running Tests

```bash
# All processor tests
pytest src/cli/tests/test_*processor*.py -v

# Migration equivalence only
pytest src/cli/tests/test_migration_equivalence.py -v

# Performance benchmarks
pytest src/cli/tests/test_processor_performance.py -v

# Production validation
pytest src/cli/tests/test_production_validation.py -v
```

## Error Handling

### Version Errors

```python
# Unsupported version
# Raises: ValueError("Unsupported version: 99.0")
processor = ProcessorFactory.create_processor("99.0")

# Invalid version format
# Raises: ValueError("Invalid version format: 'vNext'")
version = detect_version({"version": "vNext"})
```

### Validation Errors

```python
# Missing required fields
# Raises: pydantic.ValidationError
fuzzer_output = FuzzerOutput(**data_missing_fork)

# Invalid fork name
# Raises: pydantic.ValidationError
fuzzer_output = FuzzerOutput(**data_with_invalid_fork)
```

### Processing Errors

```python
# V3 with v2-only parameters (warns but continues)
# Emits: UserWarning("v3.0 format ignores v2 parameters: ...")
v3_processor.process(fuzzer_output, num_blocks=5)  # Ignored
```

## Extension Guide

### Adding v4.0 Support

1. **Create Processor**
   ```python
   # processors/v4_processor.py
   class V4Processor(BaseProcessor):
       def process(self, fuzzer_output, t8n, fork, **kwargs):
           # V4-specific logic
           pass
   ```

2. **Register Processor**
   ```python
   # processors/factory.py
   ProcessorFactory.register_processor("4.0", V4Processor)
   ```

3. **Add Tests**
   ```python
   # tests/test_v4_processor.py
   def test_v4_basic_processing():
       processor = ProcessorFactory.create_processor("4.0")
       result = processor.process(v4_output, t8n, fork)
       assert result is not None
   ```

## Best Practices

### 1. Always Use Version Detection

```python
# Good: Auto-detect version
version = detect_version(fuzzer_output)
processor = ProcessorFactory.create_processor(version)

# Avoid: Hard-coded version assumptions
processor = V2Processor()  # May fail on v3 input
```

### 2. Handle Mixed Versions Gracefully

```python
for file in input_files:
    data = load_json(file)
    version = detect_version(data)
    processor = ProcessorFactory.create_processor(version)
    result = processor.process(data, t8n, fork)
```

### 3. Validate Parameters by Version

```python
# V2: Use all parameters
v2_processor.process(data, t8n, fork, num_blocks=3, block_strategy="distribute")

# V3: Minimal parameters
v3_processor.process(data, t8n, fork)  # No num_blocks needed
```

### 4. Test Backward Compatibility

```python
# Always test both paths for v2
with patch.object(config, "use_version_processors", False):
    result_old = builder.build_blocktest(v2_data)

with patch.object(config, "use_version_processors", True):
    result_new = builder.build_blocktest(v2_data)

assert result_old == result_new  # Must be identical
```

## Troubleshooting

### "Unsupported version" Error

**Cause**: Input has version not supported by processors
**Solution**: Check `version` field in fuzzer output, ensure it's "2.0" or "3.0"

### "v3.0 format not enabled" Error

**Cause**: V3 input with `enable_v3_format=false`
**Solution**: Set `FUZZER_BRIDGE_V3=true` environment variable

### Processor Overhead Too High

**Cause**: Complex version detection or parameter validation
**Solution**: Acceptable <25%, but check for unnecessary I/O or parsing

### Mixed Version Directory Fails

**Cause**: Some files processed, others fail
**Solution**: Check error logs, ensure all files have valid version field

## References

- [V3 Fuzzer Specification](FUZZER_V3_COMPREHENSIVE_SPEC.md)
- [Implementation Summary](FUZZER_V3_IMPLEMENTATION_SUMMARY.md)
- [Test Coverage Analysis](fuzzer_bridge_coverage_gap_report.md)
- [Performance Analysis](fuzzer_bridge_performance_improvements.md)

## Changelog

### v1.0 (2025-10-10)
- ✅ Phase 1-2: Version detection and factory pattern
- ✅ Phase 3-4: V2/V3 processor implementations
- ✅ Phase 5-6: Integration with blocktest_builder and CLI
- ✅ Phase 7-8: Parallel processing and comprehensive testing
- ✅ Phase 9: Migration equivalence, performance, and production validation
- ✅ Phase 10: Documentation and deprecation planning
