# mm1 - USalign Oligomer Batch Alignment Test Framework

**mm1** is the regression test suite for USalign `-mm 1` (oligomer/multi-chain complex alignment, MMalign) combined with directory batch modes (`-dir`, `-dir1`, `-dir2`).

> **Important**: `usalign-refactor-tests-framework` must be placed in the same parent directory as the `USalign` source directory.

## Overall Hierarchy

```
D:\qlab\USalign-master\
├── USalign\                              ← source repository (USalign.cpp here)
└── usalign-refactor-tests-framework\     ← test framework repository (this repo)
    └── scripts\
        ├── cLanguage2Cplus\              ← USalign general regression & performance tests
        └── mm1\                          ← oligomer batch alignment tests (this directory)
```

## Directory Structure

```
mm1/
├── data/
│   ├── US735192405.pdb                   # Fixed target structure for -dir1/-dir2 modes
│   └── MSTATest/
│       ├── list.txt                      # PDB list for batch modes (3 structures)
│       ├── US7351924051.pdb              # RNA multi-structure alignment test data
│       ├── US7351924052.pdb
│       └── US7351924053.pdb
│
├── dir1baseline/                         # -dir1 single-pair baseline (generated from master)
├── dir2baseline/                         # -dir2 single-pair baseline
├── dirbaseline/                          # -dir  single-pair baseline
│
├── dir1result/                           # -dir1 test run output (gitignored)
├── dir2result/                           # -dir2 test run output (gitignored)
├── dirresult/                            # -dir  test run output (gitignored)
├── dir1diff/                             # -dir1 diff output (gitignored)
├── dir2diff/                             # -dir2 diff output (gitignored)
├── dirdiff/                              # -dir  diff output (gitignored)
│
├── dir1_mm1_generate_baseline.py         # -dir1 baseline generator
├── dir1_mm1_test.py                      # -dir1 test runner
├── dir1_mm1_test_cases.txt               # -dir1 regression test cases
├── dir1_mm1_feature_cases.txt            # -dir1 Guard + Batch cases
│
├── dir2_mm1_generate_baseline.py         # -dir2 baseline generator
├── dir2_mm1_test.py                      # -dir2 test runner
├── dir2_mm1_test_cases.txt               # -dir2 regression test cases
├── dir2_mm1_feature_cases.txt            # -dir2 Guard + Batch cases
│
├── dir_mm1_generate_baseline.py          # -dir  baseline generator
├── dir_mm1_test.py                       # -dir  test runner
├── dir_mm1_test_cases.txt                # -dir  regression test cases
├── dir_mm1_feature_cases.txt             # -dir  Guard + Batch cases
│
├── CLAUDE.md                             # Claude Code guide
├── IMPLEMENTATION_PLAN.txt               # Detailed implementation plan
├── WORK_LOG.txt                          # Work log
├── .gitignore                            # Ignores result/diff directories
└── README.md / README_EN.md              # This file (Chinese / English)
```

## Background

### What is mm1?

**mm1** = USalign's `-mm 1` mode, i.e., **oligomer/multi-chain complex structure alignment** (MMalign algorithm). In the original USalign code, `-dir` and `-mm 1` were hardcoded as mutually exclusive, and `-dir1` / `-dir2` produced incorrect results in `-mm 1` mode.

### New Features in USalign-beta Branch

The `USalign-beta` branch added 3 incremental functional commits to `USalign.cpp`, enabling oligomer alignment to support batch directory modes:

| Commit | Feature | Description |
|--------|---------|-------------|
| `3e5d73d` | Phase 1: `-dir1` + `-mm 1` | Each complex in directory vs fixed target |
| `ef648bf` | Phase 2: `-dir2` + `-mm 1` | Fixed query vs each complex in directory |
| `42cc64f` | Phase 3: `-dir` + `-mm 1` | Intra-directory oligomer all-vs-all (upper triangle) |

See `IMPLEMENTATION_PLAN.txt` for the full technical plan.

## Quick Start

### Prerequisites

- Python 3.x
- g++ (for compiling USalign)
- Git (the `USalign` source repository must be a Git repo with `master` and `USalign-beta` branches)
- Ensure `usalign-refactor-tests-framework` and `USalign` are in the same parent directory

### Running Tests

All commands are executed from the `mm1/` directory:

```bash
cd D:\qlab\USalign-master\usalign-refactor-tests-framework\scripts\mm1
```

#### 1. Generate Baselines (run once only)

Baselines are always compiled from the **master branch** (unmodified original version):

```bash
# -dir1 baseline
python dir1_mm1_generate_baseline.py

# -dir2 baseline
python dir2_mm1_generate_baseline.py

# -dir  baseline
python dir_mm1_generate_baseline.py
```

Each script automatically: switches to master → compiles → generates single-pair baseline → restores original branch.

#### 2. Run Regression Tests

Tests execute on the **USalign-beta branch** (or via `--branch` flag):

```bash
# -dir1 tests (regression + Guard + Batch)
python dir1_mm1_test.py

# -dir2 tests (regression + Guard + Batch)
python dir2_mm1_test.py

# -dir  tests (regression + Guard + Batch)
python dir_mm1_test.py

# Specify a different target branch
python dir_mm1_test.py --branch my-feature-branch
```

View help:

```bash
python dir_mm1_test.py --help
python dir1_mm1_test.py --help
python dir2_mm1_test.py --help
```

## Test Case Format

### Regression Test Cases (`*_test_cases.txt`)

One single-pair test case per line, tab-separated:

```
<case_name>	<workdir>	<command-line args...>
```

The workdir is relative to the project root (i.e., the parent of both `USalign/` and `usalign-refactor-tests-framework/`). Example:

```
US7351924051_vs_US7351924052	usalign-refactor-tests-framework/scripts/mm1/data/MSTATest	US7351924051.pdb US7351924052.pdb -mm 1 -ter 0
```

- Lines starting with `#` are comments
- Case names are used for naming baseline/result/diff files

### Feature Test Cases (`*_feature_cases.txt`)

Contains two types of tests:

**GUARD tests**: Verify parameter constraints, expecting program to exit with non-zero code and output a specific substring:

```
GUARD_<name>	<workdir>	<command-line args>	# EXPECT:<expected error substring>
```

**BATCH tests**: Verify batch mode output. Batch output is split by structure pair and cross-validated against single-pair baselines:

```
BATCH_<name>	<workdir>	<command-line args>
```

## Test Architecture

### Dual-Branch Strategy

The test framework detects regressions by comparing output from two versions:

| Version | Compiled From | Purpose |
|---------|---------------|---------|
| Baseline | `master` branch | Generate "gold standard" expected output |
| Current | `USalign-beta` (or specified branch) | Modified version under test |

Scripts automatically handle branch switching, compilation, testing, and restoration.

### Three-Layer Test System

Each `-dir` / `-dir1` / `-dir2` mode includes three test layers:

```
┌─────────────────────────────────────────────┐
│  1. Regression Tests                         │
│      Single-pair run → line-by-line diff vs  │
│      master baseline                         │
│      - outfmt 2 (table format)               │
│      - outfmt -1 (detailed format + rotation │
│        matrix)                               │
├─────────────────────────────────────────────┤
│  2. Guard Tests                              │
│      Verify parameter constraints & mutual   │
│      exclusion checks                        │
│      - Expect non-zero exit code             │
│      - Expect specific error substring       │
├─────────────────────────────────────────────┤
│  3. Batch Tests (Split & Cross-Validate)     │
│      Split batch output → reconstruct single │
│      pair → diff vs baseline                 │
│      - outfmt 2: split by table row          │
│      - outfmt -1: split by "Name of          │
│        Structure_1:" block                   │
└─────────────────────────────────────────────┘
```

### Smart Comparison Strategy

Output comparison yields three classifications:

| Status | Meaning |
|--------|---------|
| **PASS** | Output fully identical to baseline |
| **WARNING** | Only non-business content differs (e.g., CPU time, blank lines) |
| **FAIL** | Business content differs (alignment scores, sequences, etc.) |

This strategy avoids false positives from environmental performance fluctuations.

### Guard Test Coverage

| Constraint | Meaning |
|------------|---------|
| `-mm 2` + `-dir` | `-mm 2` (MMdock) remains prohibited with directory modes |
| `-chainmap` + directory mode | Different chain maps per pair in batch mode; global reuse prohibited |
| `-ter 2` + `-mm 1` | Oligomer mode must use `-ter 0` or `-ter 1` |
| `-o` + `-dir` | Superposed structure output prohibited in directory mode (files would overwrite) |
| `-dir` + `-dir1` mutual exclusion | Different directory mode types cannot be combined |

### Output Normalization

All output is path-normalized before writing to files:
- Windows backslashes → forward slashes
- Strip all directory prefixes (keep only filenames) for portability across machines
- No modification to any business data content

## Test Data

### Data Sources

| File | Source | Purpose |
|------|--------|---------|
| `data/US735192405.pdb` | MSTA RNA test set | Fixed target for -dir1/-dir2 |
| `data/MSTATest/US7351924051-3.pdb` | MSTA RNA test set | Test structures in batch directory |
| `data/MSTATest/list.txt` | Manually created | Structure list for batch modes |

All test structures are from the RNA multi-structure alignment test set (MSTA Test), contain multiple chains, and are suitable for verifying oligomer alignment logic.

### Generated Directories

The following directories are auto-generated at runtime and **not version-controlled** (gitignored):

- `dir1result/`, `dir2result/`, `dirresult/` — test run output
- `dir1diff/`, `dir2diff/`, `dirdiff/` — diff output

## Relationship with cLanguage2Cplus

| Dimension | cLanguage2Cplus | mm1 |
|-----------|-----------------|-----|
| Test scope | All USalign functionality | Only `-mm 1` + directory modes |
| Test type | Functional regression + performance regression | Functional regression + Guard + Batch cross-validation |
| Target branches | `master` vs current modified | `master` vs `USalign-beta` |
| Executables | `USalign_orig.exe` / `USalign_mod.exe` | `USalign_dir_mm1.exe` etc. |
| Data | Protein + RNA, various formats | RNA oligomers (MSTA test set) |

## Executable Naming

Each mode uses a separate executable to avoid file-locking conflicts on Windows:

| Mode | Executable |
|------|------------|
| `-dir1` | `USalign_dir1_mm1.exe` |
| `-dir2` | `USalign_dir2_mm1.exe` |
| `-dir` | `USalign_dir_mm1.exe` |

All executables are compiled from `../USalign/USalign.cpp` (according to the current branch), located under the `USalign/` directory.

## FAQ

### Baseline directory not found

```
[ERROR] Baseline directory not found: .../dirbaseline
```

**Solution**: Run the corresponding `generate_baseline.py` first.

### Compilation failed

```
[ERROR] Compilation failed
```

**Cause**: Usually g++ is not installed or not in PATH. Verify `g++ --version` is available.

### Branch switch failed

Ensure `../USalign/` is a Git repository with a `master` branch. The `USalign-beta` branch is only required when running tests (baseline generation only needs master).

### Single-pair baseline vs batch baseline

This framework uses a **Split Cross-Validation** strategy: baselines are only generated for single-pair output. During batch testing, batch output is split by structure pair, then compared against single-pair baselines. This means:

- No need to generate baselines for batch mode separately
- Single-pair baseline = "gold standard" for batch cross-validation
