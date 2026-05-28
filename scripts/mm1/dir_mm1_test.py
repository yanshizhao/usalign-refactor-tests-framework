#!/usr/bin/env python3
"""
Test runner for -dir + -mm 1 feature.
Runs on the target branch (default: USalign-beta), executes:
1. Regression tests: single-pair diff vs baseline
2. Guard tests: verify parameter constraints (error exit + substring)
3. Batch tests: split -dir output into pairs, diff vs single-pair baseline

Usage:
    cd USalign-master && python3 test/scripts/dir_mm1_test.py [--branch BRANCH]
"""

import os
import subprocess
import sys
import re
import argparse
import difflib

# --- paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_DIR = os.path.dirname(TEST_FRAMEWORK_DIR)
USALIGN_DIR = os.path.join(PROJECT_DIR, "USalign")

USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_dir_mm1.exe" if sys.platform == "win32" else "USalign_dir_mm1")

# Case files
REGRESSION_CASES_FILE = os.path.join(SCRIPT_DIR, "dir_mm1_test_cases.txt")
FEATURE_CASES_FILE = os.path.join(SCRIPT_DIR, "dir_mm1_feature_cases.txt")

# Directory structure
BASELINE_DIR = os.path.join(SCRIPT_DIR, "dirbaseline")
RESULT_DIR = os.path.join(SCRIPT_DIR, "dirresult")
DIFF_DIR = os.path.join(SCRIPT_DIR, "dirdiff")


# ============================================================
# Utility functions
# ============================================================
def normalize_path_in_line(line):
    """Strip ALL directory prefixes from PDB paths, keep only filename.pdb:"""
    line = re.sub(r'[A-Za-z]:[/\\]', '', line)
    line = re.sub(r'(?:[\w.\-]+[/\\])+([\w.\-]+\.pdb:)', r'\1', line)
    line = re.sub(r'[/\\]([\w.\-]+\.pdb:)', r'\1', line)
    return line

def normalize_output(text):
    """Normalize all paths in USalign output text."""
    lines = text.splitlines()
    result = []
    for line in lines:
        line = line.replace("\\", "/")
        line = normalize_path_in_line(line)
        result.append(line)
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(result) + trailing

def is_non_business_line(line_content):
    """Check if a line is non-business output (CPU time, blank line, etc.)"""
    stripped = line_content.strip()
    return not stripped or stripped.startswith('#')

def smart_compare(baseline_text, result_text):
    """
    Compare baseline and result text.
    Returns: (status, diff_text)
        status: "PASS" (identical)
                "WARN" (only non-business content differs, e.g., CPU time, blank lines)
                "FAIL" (business content differs)
    """
    diff = difflib.unified_diff(
        baseline_text.splitlines(keepends=True),
        result_text.splitlines(keepends=True),
        lineterm='\n'
    )
    diff_lines = list(diff)
    
    if not diff_lines:
        return "PASS", ""
    
    has_business_diff = False
    has_non_business_diff = False
    
    for line in diff_lines:
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
            continue
        if line.startswith('+') or line.startswith('-'):
            content = line[1:]
            if is_non_business_line(content):
                has_non_business_diff = True
            else:
                has_business_diff = True
                break
    
    diff_text = "".join(diff_lines)
    
    if has_business_diff:
        return "FAIL", diff_text
    elif has_non_business_diff:
        return "WARN", diff_text
    else:
        return "PASS", ""

def pdb_basename(path):
    """Extract base PDB name without directory and extension."""
    name = os.path.basename(str(path))
    if name.endswith(".pdb"): name = name[:-4]
    return name

def parse_pdbchain(pdbchain_str):
    """Extract PDB base name from PDBchain column value."""
    pdb_path = pdbchain_str.split(":")[0]
    return pdb_basename(pdb_path)


# ============================================================
# Test case parsing
# ============================================================
def read_regression_cases():
    cases = []
    with open(REGRESSION_CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split()
            if len(parts) < 3: continue
            name, rel_dir, command = parts[0], parts[1], parts[2:]
            work_dir = os.path.join(PROJECT_DIR, rel_dir) if rel_dir != "." else PROJECT_DIR
            pdbs = [a for a in command if a.endswith(".pdb")]
            pdb1 = pdb_basename(pdbs[0]) if len(pdbs) >= 1 else ""
            pdb2 = pdb_basename(pdbs[1]) if len(pdbs) >= 2 else ""
            cases.append({"name": name, "work_dir": work_dir, "command": command, "pdb1": pdb1, "pdb2": pdb2})
    return cases

def read_feature_cases():
    guards, batches = [], []
    with open(FEATURE_CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            expect = None
            if "# EXPECT:" in line:
                main_part, expect_part = line.split("# EXPECT:", 1)
                expect = expect_part.strip()
                line = main_part.strip()
            if not line or line.startswith("#"): continue
            parts = line.split()
            if len(parts) < 3: continue
            name, rel_dir, command = parts[0], parts[1], parts[2:]
            work_dir = os.path.join(PROJECT_DIR, rel_dir) if rel_dir != "." else PROJECT_DIR
            if name.startswith("GUARD_"):
                guards.append({"name": name, "work_dir": work_dir, "command": command, "expect": expect})
            elif name.startswith("BATCH_"):
                batches.append({"name": name, "work_dir": work_dir, "command": command})
    return guards, batches


# ============================================================
# Build & branch
# ============================================================
def current_branch():
    result = subprocess.run(["git", "-C", USALIGN_DIR, "branch", "--show-current"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Failed to get current branch!")
        sys.exit(1)
    return result.stdout.strip()


def git_checkout(branch):
    current = current_branch()
    if current != branch:
        print(f"  Switching from '{current}' to '{branch}'...")
        result = subprocess.run(["git", "-C", USALIGN_DIR, "checkout", branch], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] git checkout '{branch}' failed!")
            sys.exit(1)
    else:
        print(f"  Already on '{branch}'")

def compile_usalign():
    env = os.environ.copy()
    env["TMPDIR"] = "/tmp"
    result = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-static", "USalign.cpp", "-o", "USalign_dir_mm1", "-lm"],
        cwd=USALIGN_DIR, env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[ERROR] Compilation failed:\n{result.stderr}")
        sys.exit(1)
    print("  Compilation OK")


# ============================================================
# Run USalign
# ============================================================
def run_usalign(work_dir, command):
    args = [USALIGN_EXE] + command
    result = subprocess.run(args, capture_output=True, text=True, timeout=600, cwd=work_dir)
    return result.returncode, result.stdout, result.stderr


# ============================================================
# Step 2: Regression tests
# ============================================================
def show_diff_preview(diff_text, max_lines=10):
    lines = diff_text.strip().splitlines()
    for line in lines[:max_lines]: print(f"      {line}")
    if len(lines) > max_lines: print(f"      ... ({len(lines) - max_lines} more lines)")

def run_regression_tests(cases):
    print(f"\n[Step 2] Regression tests: {len(cases)} cases")
    print("-" * 50)
    passed, warned, failed = 0, 0, 0
    for case in cases:
        name, work_dir, command = case["name"], case["work_dir"], case["command"]
        case_status = "PASS"
        for outfmt in [2, -1]:
            fmt_str = "outfmt-1" if outfmt == -1 else f"outfmt{outfmt}"
            baseline_file = os.path.join(BASELINE_DIR, f"{name}_{fmt_str}.txt")
            result_file = os.path.join(RESULT_DIR, f"{name}_{fmt_str}.txt")
            diff_file = os.path.join(DIFF_DIR, f"{name}_{fmt_str}.diff")

            if not os.path.exists(baseline_file):
                print(f"  {name} [{fmt_str}] SKIP (no baseline)")
                case_status = "FAIL"
                continue

            full_cmd = command + ["-outfmt", str(outfmt)]
            if outfmt == -1: full_cmd.extend(["-m", "-"])
            rc, stdout, stderr = run_usalign(work_dir, full_cmd)
            output = stdout + stderr
            if rc != 0:
                print(f"  {name} [{fmt_str}] FAIL (exit code {rc})")
                case_status = "FAIL"
                continue

            norm_result = normalize_output(output)
            with open(result_file, "w", encoding="utf-8") as f: f.write(norm_result)
            with open(baseline_file, "r", encoding="utf-8") as f: baseline_text = f.read()

            status, diff_text = smart_compare(baseline_text, norm_result)
            
            if status == "FAIL":
                with open(diff_file, "w", encoding="utf-8") as f: f.write(diff_text)
                print(f"  {name} [{fmt_str}] FAIL (business content mismatch)")
                show_diff_preview(diff_text)
                case_status = "FAIL"
            elif status == "WARN":
                with open(diff_file, "w", encoding="utf-8") as f: f.write(diff_text)
                print(f"  {name} [{fmt_str}] WARNING (non-business content mismatch)")
                show_diff_preview(diff_text)
                if case_status != "FAIL": case_status = "WARN"
            else:
                print(f"  {name} [{fmt_str}] PASS")

        if case_status == "FAIL": failed += 1
        elif case_status == "WARN": warned += 1; passed += 1
        else: passed += 1
                
    return passed, warned, failed


# ============================================================
# Step 3: Guard tests
# ============================================================
def run_guard_tests(guards):
    print(f"\n[Step 3] Guard tests: {len(guards)} cases")
    print("-" * 50)
    passed, failed = 0, 0
    for guard in guards:
        name, work_dir, command, expect = guard["name"], guard["work_dir"], guard["command"], guard["expect"]
        rc, stdout, stderr = run_usalign(work_dir, command)
        combined = stdout + stderr
        if rc == 0:
            print(f"  {name} FAIL (expected error exit, got rc=0)")
            failed += 1
            continue
        if expect and expect not in combined:
            print(f"  {name} FAIL (expected '{expect}' not found)")
            print(f"    output: {combined.strip()[:200]}")
            failed += 1
            continue
        print(f"  {name} PASS (rc={rc}, found '{expect}')")
        passed += 1
    return passed, failed


# ============================================================
# Step 4: Batch tests (Split & Diff)
# ============================================================
def build_case_lookup(regression_cases):
    """Build lookup: (pdb1_base, pdb2_base) -> case. Strict order, no reverse."""
    lookup = {}
    for case in regression_cases:
        key = (case["pdb1"], case["pdb2"])
        lookup[key] = case
    return lookup

def compare_split_vs_baseline(case_name, fmt_str, reconstructed_text):
    """Compare reconstructed split text against baseline file. Returns (status, error_msg)."""
    baseline_file = os.path.join(BASELINE_DIR, f"{case_name}_{fmt_str}.txt")
    result_file = os.path.join(RESULT_DIR, f"split_{case_name}_{fmt_str}.txt")
    diff_file = os.path.join(DIFF_DIR, f"split_{case_name}_{fmt_str}.diff")

    if not os.path.exists(baseline_file):
        return "FAIL", f"No baseline file: {baseline_file}"

    norm_result = normalize_output(reconstructed_text)
    with open(result_file, "w", encoding="utf-8") as f: f.write(norm_result)

    with open(baseline_file, "r", encoding="utf-8") as f: baseline_text = f.read()

    status, diff_text = smart_compare(baseline_text, norm_result)

    if status == "FAIL":
        with open(diff_file, "w", encoding="utf-8") as f: f.write(diff_text)
        return "FAIL", f"{case_name} {fmt_str} BUSINESS CONTENT mismatch"
    elif status == "WARN":
        with open(diff_file, "w", encoding="utf-8") as f: f.write(diff_text)
        return "WARN", f"{case_name} {fmt_str} non-business content mismatch"
    
    return "PASS", None

def split_and_diff_outfmt2(batch_output, case_lookup):
    """Split outfmt 2 tabular output, reconstruct with header, diff vs baseline."""
    lines = batch_output.strip().splitlines()
    if len(lines) < 2: return ["outfmt 2 output too short"], [], []

    fails, warns, passes = [], [], []
    header = lines[0]
    for line in lines[1:]:
        cols = line.strip().split()
        if len(cols) < 2: continue

        p1 = parse_pdbchain(cols[0])
        p2 = parse_pdbchain(cols[1])

        case = case_lookup.get((p1, p2))
        if not case:
            fails.append(f"No baseline for pair ({p1}, {p2})")
            continue

        reconstructed = header + "\n" + line.strip() + "\n"
        status, msg = compare_split_vs_baseline(case["name"], "outfmt2", reconstructed)
        if status == "FAIL": fails.append(msg)
        elif status == "WARN": warns.append(msg)
        else: passes.append(msg)

    return fails, warns, passes

def split_and_diff_outfmt_m1(batch_output, case_lookup):
    """Split outfmt -1 detailed output by blocks, diff vs baseline."""
    blocks = re.split(r'(?=Name of Structure_1:)', batch_output.strip())
    fails, warns, passes = [], [], []

    for block in blocks:
        if 'Name of Structure_1:' not in block:
            continue

        m1 = re.search(r'Name of Structure_1:\s*(\S+)', block)
        m2 = re.search(r'Name of Structure_2:\s*(\S+)', block)
        p1 = parse_pdbchain(m1.group(1)) if m1 else ""
        p2 = parse_pdbchain(m2.group(1)) if m2 else ""

        case = case_lookup.get((p1, p2))
        if not case:
            fails.append(f"No baseline for pair ({p1}, {p2})")
            continue

        reconstructed = block.strip() + "\n"
        status, msg = compare_split_vs_baseline(case["name"], "outfmt-1", reconstructed)
        if status == "FAIL": fails.append(msg)
        elif status == "WARN": warns.append(msg)
        else: passes.append(msg)

    return fails, warns, passes

def run_batch_tests(batches, regression_cases):
    print(f"\n[Step 4] Batch tests: {len(batches)} cases")
    print("-" * 50)
    case_lookup = build_case_lookup(regression_cases)
    
    # Statistical dimension 1: BATCH case level
    batch_passed, batch_failed = 0, 0
    # Statistical dimension 2: split pair level
    total_split_pass, total_split_warn, total_split_fail = 0, 0, 0

    for batch in batches:
        name, work_dir, command = batch["name"], batch["work_dir"], batch["command"]

        outfmt = None
        for i, arg in enumerate(command):
            if arg == "-outfmt" and i + 1 < len(command):
                outfmt = int(command[i + 1])
                break

        print(f"  {name} (outfmt={outfmt}) ... ", end="", flush=True)
        rc, stdout, stderr = run_usalign(work_dir, command)
        output = stdout + stderr

        if rc != 0:
            print(f"FAIL (exit code {rc})")
            batch_failed += 1
            continue

        # Save raw output
        result_file = os.path.join(RESULT_DIR, f"{name}_raw.txt")
        with open(result_file, "w", encoding="utf-8") as f: f.write(normalize_output(output))

        # Split and diff
        errs, warns, passes = [], [], []
        if outfmt == 2:
            errs, warns, passes = split_and_diff_outfmt2(output, case_lookup)
        elif outfmt == -1:
            errs, warns, passes = split_and_diff_outfmt_m1(output, case_lookup)
        else:
            errs.append(f"Unsupported outfmt={outfmt} for batch cross-validation")

        # Accumulate split pair level statistics
        total_split_fail += len(errs)
        total_split_warn += len(warns)
        total_split_pass += len(passes)

        # Print current BATCH case result and accumulate BATCH level statistics
        if errs:
            print(f"FAIL ({len(errs)} business mismatch(es))")
            for err in errs: print(f"    {err}")
            batch_failed += 1
        elif warns:
            print(f"WARNING ({len(warns)} non-business mismatch(es), {len(passes)} strictly passed)")
            for w in warns: print(f"    {w}")
            batch_passed += 1
        else:
            print(f"PASS ({len(passes)} pairs strictly matched)")
            batch_passed += 1

    return batch_passed, batch_failed, total_split_pass, total_split_warn, total_split_fail


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Test runner for -dir + -mm 1")
    parser.add_argument("--branch", default="USalign-beta", help="Target branch to test (default: USalign-beta)")
    args = parser.parse_args()

    print("=" * 60)
    print("Test Runner: -dir + -mm 1")
    print("=" * 60)

    regression_cases = read_regression_cases()
    guards, batches = read_feature_cases()
    print(f"\nRegression cases: {len(regression_cases)}")
    print(f"Guard cases: {len(guards)}")
    print(f"Batch cases: {len(batches)}")

    if not os.path.exists(BASELINE_DIR):
        print(f"\n[ERROR] Baseline directory not found: {BASELINE_DIR}")
        print(f"  Run generate_dir_mm1_baseline.py first!")
        sys.exit(1)

    # Step 1: Checkout target branch & compile
    original_branch = current_branch()
    try:
        print(f"\n[Step 1] Checkout '{args.branch}' & compile")
        git_checkout(args.branch)
        compile_usalign()

        os.makedirs(RESULT_DIR, exist_ok=True)
        os.makedirs(DIFF_DIR, exist_ok=True)

        # Step 2: Regression tests
        reg_pass, reg_warn, reg_fail = run_regression_tests(regression_cases)

        # Step 3: Guard tests
        guard_pass, guard_fail = run_guard_tests(guards)

        # Step 4: Batch tests
        batch_pass, batch_fail, split_pass, split_warn, split_fail = run_batch_tests(batches, regression_cases)

    finally:
        if original_branch and original_branch != current_branch():
            print(f"[Restore] Switching USalign back to '{original_branch}'")
            git_checkout(original_branch)

    # Step 5: Summary
    total_pass = reg_pass + guard_pass + batch_pass
    total_warn = reg_warn + split_warn
    total_fail = reg_fail + guard_fail + batch_fail
    
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Regression: {reg_pass} passed, {reg_warn} warned, {reg_fail} failed")
    print(f"  Guard:      {guard_pass} passed, {guard_fail} failed")
    print(f"  Batch:      {batch_pass} batches passed, {batch_fail} batches failed")
    print(f"              ({split_pass + split_warn + split_fail} splits: {split_pass} strictly passed, {split_warn} warned, {split_fail} failed)")
    print(f"  ---------------------------------------------------")
    print(f"  Total:      {total_pass} test suites passed, {total_warn} sub-tests warned, {total_fail} failed")

    if total_fail > 0:
        print("\n[FAIL] TESTS FAILED")
        sys.exit(1)
    elif total_warn > 0:
        print("\n[WARN] TESTS PASSED WITH WARNINGS (Non-business content mismatches detected)")
        sys.exit(0)
    else:
        print("\n[PASS] ALL TESTS PASSED STRICTLY")
        sys.exit(0)

if __name__ == "__main__":
    main()
