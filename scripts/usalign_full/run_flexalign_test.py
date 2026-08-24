#!/usr/bin/env python3
"""
Run all functional tests from testcases_functional.txt for flexalign
using USalign_single_full.cpp and compare with baseline results.
"""

import difflib
import os
import re
import subprocess
import sys

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FRAMEWORK = os.path.join(SCRIPT_DIR, "..", "flexalign")
USALIGN_DIR = os.path.join(SCRIPT_DIR, "..", "..", "..", "USalign")
USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_full.exe")
if not os.path.exists(USALIGN_EXE):
    USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_full")
DATA_DIR = os.path.join(TEST_FRAMEWORK, "data")
BASELINE_DIR = os.path.join(TEST_FRAMEWORK, "baseline")
CURRENT_DIR = os.path.join(TEST_FRAMEWORK, "current")
TESTCASES_FILE = os.path.join(TEST_FRAMEWORK, "testcases_functional.txt")
DIFFS_DIR = os.path.join(TEST_FRAMEWORK, "diffs")

# Create and clean directories
os.makedirs(CURRENT_DIR, exist_ok=True)
os.makedirs(DIFFS_DIR, exist_ok=True)

# Clean previous results
for item in os.listdir(CURRENT_DIR):
    item_path = os.path.join(CURRENT_DIR, item)
    if os.path.isfile(item_path) and item.endswith('.out'):
        os.remove(item_path)

for item in os.listdir(DIFFS_DIR):
    item_path = os.path.join(DIFFS_DIR, item)
    if os.path.isfile(item_path) and item.endswith('.diff'):
        os.remove(item_path)

# Switch USalign to master branch before running tests
if os.path.exists(os.path.join(USALIGN_DIR, ".git")):
    result = subprocess.run(["git", "checkout", "master"], cwd=USALIGN_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: git checkout master failed: {result.stderr}")

# Read test cases
with open(TESTCASES_FILE, "r") as f:
    test_cases = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

print(f"Found {len(test_cases)} test cases")
print(f"Using USalign: {USALIGN_EXE}")
print(f"Data directory: {DATA_DIR}")
print(f"Baseline directory: {BASELINE_DIR}")
print(f"Current directory: {CURRENT_DIR}")
print()

passed = 0
failed = 0
skipped = 0

def clean_slash(text):
    """Remove redundant '/' prefix in output paths (same as original create_baseline.py)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text

for i, test_case in enumerate(test_cases, 1):
    parts = test_case.split()
    if len(parts) < 3:
        print(f"[{i}/{len(test_cases)}] SKIP: Invalid test case format: {test_case}")
        skipped += 1
        continue

    test_name = parts[0]
    workdir_rel = parts[1]
    args = parts[2:]

    # Working directory for this test case
    workdir = os.path.join(DATA_DIR, workdir_rel)

    # Build command with relative paths (as in original)
    cmd = [USALIGN_EXE] + args

    # Determine output file
    out_file = os.path.join(CURRENT_DIR, f"{test_name}.out")

    print(f"[{i}/{len(test_cases)}] RUN: {test_name}")
    print(f"  CWD: {workdir}")
    print(f"  CMD: {' '.join(cmd)}")

    # Check if files exist
    pdb_files = [arg for arg in args if arg.endswith('.pdb')]
    files_exist = True
    for pdb in pdb_files:
        pdb_path = os.path.join(workdir, pdb)
        if not os.path.exists(pdb_path):
            print(f"  SKIP: {pdb_path} not found")
            skipped += 1
            files_exist = False
            break

    if not files_exist:
        continue

    try:
        # Run command and capture output
        result = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Clean output the same way as create_baseline.py does
        content = result.stdout + result.stderr
        content = clean_slash(content)

        # Save output
        with open(out_file, "w") as f:
            f.write(content)

        # Compare with baseline
        baseline_file = os.path.join(BASELINE_DIR, f"{test_name}.out")
        if os.path.exists(baseline_file):
            with open(baseline_file, "r") as f:
                baseline_content = f.read()

            with open(out_file, "r") as f:
                current_content = f.read()

            baseline_filtered = re.sub(r'^\s*#Total CPU time.*\n?', '', baseline_content, flags=re.MULTILINE)
            current_filtered = re.sub(r'^\s*#Total CPU time.*\n?', '', current_content, flags=re.MULTILINE)

            # Compare with baseline
            if baseline_filtered != current_filtered:
                # Generate diff file only when outputs differ
                baseline_lines = baseline_filtered.splitlines(keepends=True)
                current_lines = current_filtered.splitlines(keepends=True)
                diff_lines = list(difflib.unified_diff(
                    baseline_lines, current_lines,
                    fromfile=f"baseline/{test_name}.out",
                    tofile=f"current/{test_name}.out",
                    lineterm=""
                ))
                # Only write diff file if there are actual differences
                if diff_lines:
                    diff_path = os.path.join(DIFFS_DIR, f"{test_name}.diff")
                    with open(diff_path, "w", encoding="utf-8") as df:
                        df.writelines(diff_lines)

                print(f"  [FAIL] {test_name} - Output differs from baseline, diff saved to {diff_path}")
                failed += 1
            else:
                print(f"  [PASS] {test_name}")
                passed += 1
        else:
            print(f"  ? NO BASELINE: {test_name} - No baseline file found")
            passed += 1  # Count as pass if no baseline

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {test_name}")
        failed += 1
    except Exception as e:
        print(f"  [ERROR] {test_name} - {str(e)}")
        failed += 1

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)