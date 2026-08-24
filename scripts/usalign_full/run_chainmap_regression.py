#!/usr/bin/env python3
"""
Run regression tests from testcases_regression.txt for chainmap functionality
using USalign_full.exe and compare with baseline results.
"""

import difflib
import os
import re
import shutil
import subprocess
import sys
import platform

# Paths - relative to script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "chainmap_local", "data")
CURRENT_DIR = os.path.join(SCRIPT_DIR, "..", "chainmap_local", "current")
BASELINE_DIR = os.path.join(SCRIPT_DIR, "..", "chainmap_local", "baseline")
TESTCASES_FILE = os.path.join(SCRIPT_DIR, "..", "chainmap_local", "testcases_regression.txt")
DIFFS_DIR = os.path.join(SCRIPT_DIR, "..", "chainmap_local", "diffs")
USALIGN_DIR = os.path.join(SCRIPT_DIR, "..", "..", "..", "USalign")
USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_full.exe")
if not os.path.exists(USALIGN_EXE):
    USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_full")


# Switch USalign to master branch before running tests
def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: git branch failed: {result.stderr}")
        return None
    return result.stdout.strip()

def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: git checkout {branch} failed: {result.stderr}")
        return False
    return True

def compile_usalign():
    src = os.path.join(str(USALIGN_DIR), "USalign_single_full.cpp")
    exe = USALIGN_EXE
    print(f"Compiling {src} -> {exe}")
    compile_cmd = ["g++", "-O3", "-ffast-math", "-o", exe, src]
    if platform.system() == "Windows":
        compile_cmd.insert(3, "-static-libgcc")
        compile_cmd.insert(4, "-static-libstdc++")
    if subprocess.run(compile_cmd).returncode != 0:
        print("Compilation failed!")
        sys.exit(1)
    print("Compilation successful!")

def clean_slash(text):
    """Remove redundant '/' prefix in output paths (same as original create_baseline.py)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text

def strip_cpu_time(text):
    return re.sub(r'^\s*#Total CPU time.*\n?', '', text, flags=re.MULTILINE)

def is_non_business_line(line):
    stripped = line.strip()
    if not stripped:
        return True
    if "#Total CPU time" in stripped:
        return True
    return False


# Create and clean directories
if os.path.exists(CURRENT_DIR):
    shutil.rmtree(CURRENT_DIR, ignore_errors=True)
    os.makedirs(CURRENT_DIR, exist_ok=True)
else:
    os.makedirs(CURRENT_DIR, exist_ok=True)

if os.path.exists(DIFFS_DIR):
    shutil.rmtree(DIFFS_DIR, ignore_errors=True)
os.makedirs(DIFFS_DIR, exist_ok=True)

# Compile and switch to master
original_branch = None
if os.path.exists(os.path.join(USALIGN_DIR, ".git")):
    original_branch = current_branch()
    if original_branch and original_branch != "master":
        print(f"Switching USalign from {original_branch} to master for compilation...")
        checkout("master")
    compile_usalign()
    if original_branch and original_branch != "master":
        print(f"Restoring USalign branch to {original_branch}...")
        checkout(original_branch)

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
warned = 0

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

            baseline_filtered = strip_cpu_time(baseline_content)
            current_filtered = strip_cpu_time(current_content)

            # Generate diff file when outputs differ
            if baseline_filtered != current_filtered:
                # Generate unified diff
                baseline_lines = baseline_filtered.splitlines(keepends=True)
                current_lines = current_filtered.splitlines(keepends=True)
                diff_lines = list(difflib.unified_diff(
                    baseline_lines, current_lines,
                    fromfile=f"baseline/{test_name}.out",
                    tofile=f"current/{test_name}.out",
                    lineterm=""
                ))
                # Write diff file
                diff_path = os.path.join(DIFFS_DIR, f"{test_name}.diff")
                with open(diff_path, "w", encoding="utf-8") as df:
                    df.writelines(diff_lines)

                # Check if only CPU time differs
                business_diff = [l for l in diff_lines
                                 if (l.startswith("+") or l.startswith("-"))
                                 and not l.startswith(("+++", "---"))
                                 and not is_non_business_line(l)]
                if business_diff:
                    print(f"  [FAIL] {test_name} - Output differs from baseline, diff saved to {diff_path}")
                    failed += 1
                else:
                    print(f"  [WARNING] {test_name} - Only CPU time differs")
                    warned += 1
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
print(f"Results: {passed} passed, {warned} warning, {failed} failed, {skipped} skipped")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)