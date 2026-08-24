# USalign_full Test Scripts Directory

## 📋 Prerequisites Before Running Scripts (Must Read)

Before running any test script, make sure the following steps are completed:

1. **Switch to the master branch**:
   - Open a terminal and navigate to the `us-align_modify\USalign` directory
   - Run `git checkout master` to switch to the master branch

2. **Pull the latest commits**:
   - Run `git pull` to get the latest commits
   - Make sure the USalign source code is up to date

3. **Place the source file**:
   - Put the `USalign_single_full.cpp` file into the `us-align_modify\USalign` directory
   - Make sure the file path is correct: `us-align_modify\USalign\USalign_single_full.cpp`

4. **Return to this directory**:
   - After completing the above steps, return to the `scripts/usalign_full/` directory
   - You can now start running the test scripts

> **Note**: All test scripts (`run_full_test.py`, `run_flexalign_test.py`, `run_chainmap_regression.py`) will automatically try to switch to the master branch when compiling USalign, but it is recommended to manually complete the above steps before running to ensure the environment is ready.

---

This directory contains automated test scripts related to **USalign_full**. These scripts are used to run functional tests and regression tests, and compare the current output with baseline results to verify the correctness of code changes.

---

## 📁 Directory Structure

```
scripts/usalign_full/
├── run_full_test.py          # cLanguage2Cplus test set: testcases_baseline_functional.txt
├── run_flexalign_test.py     # flexalign test set: testcases_functional.txt
├── run_chainmap_regression.py # chainmap_local test set: testcases_baseline_functional.txt
└── README_English.md          # This file
```

---

## 🚀 Quick Start

### Prerequisites

1. The **USalign repository** must be located at `../../../USalign/` (relative to this script directory)
2. The **USalign executable** is compiled automatically: `USalign/USalign_full.exe` or `USalign/USalign_full`
3. **Test data** is located in the `data/` directory of each test framework
4. **Baseline files** are located in the `baseline/` directory of each test framework
5. **Python 3** environment

---

## 📋 Detailed Script Description

### 1. `run_full_test.py` - cLanguage2Cplus test set: testcases_baseline_functional.txt

**Purpose**: Runs the test set from testcases_baseline_functional.txt, executes with **USalign_full.exe**, and compares with baseline results.

**Test data locations**:
- Test case file: `scripts/cLanguage2Cplus/testcases_baseline_functional.txt`
- Data directory: `scripts/cLanguage2Cplus/data/`
- Baseline directory: `scripts/cLanguage2Cplus/baseline/`
- Current output: `scripts/cLanguage2Cplus/current/`
- Diff files: `scripts/cLanguage2Cplus/diffs/`

**Usage**:
```bash
cd scripts/usalign_full
python3 run_full_test.py
```

**Test case format** (one test case per line):
```
test_name workdir_rel pdb1 pdb2 [additional_args...]
```

**Features**:
- Automatically switches to USalign's `master` branch for compilation
- Restores the original branch after running
- Cleans up output files from the previous test run
- Timeout: 60 seconds
- Ignores CPU time differences (only compares actual output content)
- Generates uniformly formatted diff files

---

### 2. `run_flexalign_test.py` - flexalign test set: testcases_functional.txt

**Purpose**: Runs the test set from testcases_functional.txt, using the executable compiled from **USalign_single_full.cpp**.

**Test data locations**:
- Test case file: `scripts/flexalign/testcases_functional.txt`
- Data directory: `scripts/flexalign/data/`
- Baseline directory: `scripts/flexalign/baseline/`
- Current output: `scripts/flexalign/current/`
- Diff files: `scripts/flexalign/diffs/`

**Usage**:
```bash
cd scripts/usalign_full
python3 run_flexalign_test.py
```

**Test case format**:
```
test_name workdir_rel pdb_file1 [pdb_file2...] [additional_args...]
```

**Features**:
- Automatically checks whether PDB files exist
- Skips the test case if the file does not exist
- Automatically cleans up redundant `/` characters in paths
- Supports Windows static linking compilation

---

### 3. `run_chainmap_regression.py` - chainmap_local test set: testcases_baseline_functional.txt

**Purpose**: Runs the test set from testcases_baseline_functional.txt, verifying that code changes do not break existing functionality.

**Test data locations**:
- Test case file: `scripts/chainmap_local/testcases_regression.txt`
- Data directory: `scripts/chainmap_local/data/`
- Baseline directory: `scripts/chainmap_local/baseline/`
- Current output: `scripts/chainmap_local/current/`
- Diff files: `scripts/chainmap_local/diffs/`

**Usage**:
```bash
cd scripts/usalign_full
python3 run_chainmap_regression.py
```

**Features**:
- Completely cleans and rebuilds the `current/` and `diffs/` directories
- Intelligently detects diff types:
  - If only CPU time differs, marked as **WARNING**
  - If actual business logic output differs, marked as **FAIL**
- Provides more detailed diff classification

---

## 🔧 Common Configuration

### Environment Variables

All scripts support the following environment variables (optional):

| Variable | Default | Description |
|----------|---------|-------------|
| None | - | Scripts currently do not use environment variables; all paths are hardcoded relative paths |

### Compilation Options

All scripts use the following options when compiling USalign:
```bash
g++ -O3 -ffast-math -o USalign_full USalign.cpp
```

**Windows platform**:
```bash
g++ -static -O3 -ffast-math -lm -o USalign_full.exe USalign.cpp
```

---

## 📊 Output Format

### Test Progress Display

```
[1/10] RUN: test_case_name
  CWD: /path/to/data/directory
  CMD: USalign_full pdb1.pdb pdb2.pdb -option value
  [PASS] test_case_name

[2/10] RUN: another_test
  CWD: /path/to/data/directory  
  CMD: USalign_full file1.pdb file2.pdb
  [FAIL] another_test - Output differs from baseline, diff saved to scripts/.../diffs/another_test.diff
```

### Final Summary

**run_full_test.py and run_flexalign_test.py**:
```
============================================================
Results: 45 passed, 2 failed, 1 skipped
============================================================
```

**run_chainmap_regression.py**:
```
============================================================
Results: 45 passed, 1 warning, 2 failed, 1 skipped
============================================================
```

---

## 🎯 Test Case File Format

### testcases_baseline_functional.txt (used by run_full_test.py)

```
# Comment lines (start with #)
# Format: test_name workdir_rel pdb1 pdb2 [args...]

# Example:
test_1h05 1h05 1h05.pdb 1h05.pdb -ter 0
test_1x8a 1x8a 1x8a.pdb 1x8a.pdb -ter 1
```

### testcases_functional.txt (used by run_flexalign_test.py)

```
# Format: test_name workdir_rel pdb_file1 [pdb_file2...] [args...]
test_flex_001 chain_001 chainA.pdb chainB.pdb -flex
```

### testcases_regression.txt (used by run_chainmap_regression.py)

```
# Format: test_name workdir_rel args...
test_chain_001 dir001 file1.pdb file2.pdb -chain
```

---

## 🔍 Diff Files

When a test fails, the script generates a diff file (`.diff`) saved to the corresponding `diffs/` directory.

Diff files use the **unified diff** format:

```diff
--- baseline/test_name.out
+++ current/test_name.out
@@ -1,5 +1,5 @@
 line1
-line2_old
+line2_new
 line3
```

---

## ⚙️ Custom Tests

### Adding New Test Cases

1. Add a new line to the corresponding `testcases_*.txt` file
2. Make sure the test data files exist in the `data/` directory
3. Run the test to generate current output
4. Copy the output to the `baseline/` directory as the baseline

### Creating a Baseline

You can use the `create_baseline.py` script to create baseline files. For example:

```bash
# First run a test to generate current/ output
python3 run_full_test.py

# Then copy current/ to baseline/
cp -r scripts/cLanguage2Cplus/current/* scripts/cLanguage2Cplus/baseline/
```

---

## 📝 Output Cleaning Rules

All scripts clean the USalign output to ensure consistent comparison:

1. **Remove redundant `/` characters**:
   ```python
   # Remove "/" from "Name of Structure_1: /path/to/file"
   re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', content)
   
   # Remove "/" at the beginning of a line or after a tab/space (when followed by an uppercase letter)
   re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', content, flags=re.MULTILINE)
   ```

2. **Ignore CPU time lines**:
   ```python
   # Remove all "#Total CPU time..." lines
   re.sub(r'^\s*#Total CPU time.*\n?', '', content, flags=re.MULTILINE)
   ```

---

## 🔄 Git Branch Handling

Before compiling, all scripts will:

1. Check whether the USalign repository is a Git repository
2. Record the current branch
3. Switch to the `master` branch for compilation
4. Automatically switch back to the original branch after compilation

**Note**: If USalign is not a Git repository, the current state is used directly for compilation.

---

## 📈 Return Values

Exit codes of all scripts:
- **0**: All tests passed (`failed == 0`)
- **1**: Some tests failed (`failed > 0`)

---

## 📚 Related Directories

| Directory | Purpose |
|-----------|---------|
| `scripts/cLanguage2Cplus/` | Main functional test framework |
| `scripts/flexalign/` | FlexAlign test framework |
| `scripts/chainmap_local/` | ChainMap regression test framework |
| `../../../USalign/` | USalign source code repository |

---

## 💡 Usage Tips

1. **Update baselines regularly**: Regenerate baseline files when USalign code has major changes
2. **Check diff files**: When tests fail, carefully review the generated `.diff` files to understand the specific differences
3. **Run in batches**: If there are many test cases, you can temporarily modify the test case file to run only a subset of tests
4. **Save logs**: It is recommended to redirect test output to a log file: `python3 run_full_test.py 2>&1 | tee test_log.txt`

---

## 🔗 Quick Links

- [USalign main repository](../../../USalign/)
- [Test framework root](../../)
- [cLanguage2Cplus test framework](../cLanguage2Cplus/)
- [FlexAlign test framework](../flexalign/)
- [ChainMap test framework](../chainmap_local/)

---

*Last updated: 2026-08-24*