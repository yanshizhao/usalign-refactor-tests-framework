#!/usr/bin/env python3
"""
Test runner for -dir2 + -mm 1 feature. (V7.1 Compliant)
Runs on the target branch, executes:
1. Regression tests: single-pair diff vs baseline
2. Guard tests: verify parameter constraints
3. Batch tests: split output, cross-validate vs single-pair baselines
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
USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_dir2_mm1.exe" if sys.platform == "win32" else "USalign_dir2_mm1")

REGRESSION_CASES_FILE = os.path.join(SCRIPT_DIR, "dir2_mm1_test_cases.txt")
FEATURE_CASES_FILE = os.path.join(SCRIPT_DIR, "dir2_mm1_feature_cases.txt")
BASELINE_DIR = os.path.join(SCRIPT_DIR, "dir2baseline")
RESULT_DIR = os.path.join(SCRIPT_DIR, "dir2result")
DIFF_DIR = os.path.join(SCRIPT_DIR, "dir2diff")


def clean_result_dirs():
    """V7.1: Clean historical result and diff files before each test run."""
    for dir_path in [RESULT_DIR, DIFF_DIR]:
        if os.path.exists(dir_path):
            count = 0
            for fname in os.listdir(dir_path):
                fpath = os.path.join(dir_path, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    count += 1
            if count > 0:
                print(f"  Cleaned {count} file(s) from {os.path.basename(dir_path)}/")
        os.makedirs(dir_path, exist_ok=True)


# ============================================================
# Utility functions (V7.1: No data tampering, all extensions)
# ============================================================
def normalize_path_in_line(line):
    """Strip ALL directory prefixes from file paths, keep only filename.ext:"""
    line = re.sub(r'[A-Za-z]:[/\\]', '', line)
    line = re.sub(r'(?:[\w.\-]+[/\\])+([\w.\-]+\.\w+:)', r'\1', line)
    line = re.sub(r'[/\\]([\w.\-]+\.\w+:)', r'\1', line)
    return line

def normalize_output(text):
    """Normalize all paths in output text. NO content stripping."""
    lines = text.splitlines()
    result = []
    for line in lines:
        line = line.replace("\\", "/")
        line = normalize_path_in_line(line)
        result.append(line)
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(result) + trailing

def is_non_business_line(line):
    stripped = line.strip()
    if not stripped: return True
    if "#Total CPU time is" in stripped: return True
    return False

def smart_compare(baseline_path, result_path, tag):
    """V7.1 Extreme simple strategy: Business=FAIL, Environment=WARNING"""
    if not os.path.exists(baseline_path):
        print("SKIP (no baseline)"); return "SKIP"

    with open(baseline_path, "r", encoding="utf-8", errors="replace") as fb, \
         open(result_path, "r", encoding="utf-8", errors="replace") as fr:
        blines = fb.readlines()
        rlines = fr.readlines()

    diff = difflib.unified_diff(blines, rlines,
                                fromfile=f"baseline/{os.path.basename(baseline_path)}",
                                tofile=f"result/{os.path.basename(result_path)}")
    diff_text = "".join(diff)

    if not diff_text:
        print("PASS"); return "PASS"

    status = "PASS"
    for line in diff_text.splitlines():
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@') or line.startswith(' '):
            continue
        content = line[1:].strip()
        if line.startswith('-') or line.startswith('+'):
            if is_non_business_line(content):
                status = "WARNING" if status != "FAIL" else "FAIL"
            else:
                status = "FAIL"; break

    if status != "PASS":
        diff_file = os.path.join(DIFF_DIR, f"{tag}.diff")
        with open(diff_file, "w", encoding="utf-8") as df:
            df.write(diff_text)
    print(status)
    return status

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
            cases.append({"name": name, "work_dir": work_dir, "command": command})
    return cases

def read_feature_cases():
    guards, batches = [], []
    with open(FEATURE_CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            expect = None
            if "# EXPECT:" in line:
                main_part, expect_part = line.split("# EXPECT:", 1)
                expect = expect_part.strip(); line = main_part.strip()
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

def build_regression_map(cases):
    """Build ordered mapping: (pdb1_basename, pdb2_basename) -> case_name"""
    mapping = {}
    for case in cases:
        pdbs = [os.path.splitext(os.path.basename(p))[0].lower()
                for p in case["command"] if p.endswith(".pdb")]
        if len(pdbs) >= 2:
            mapping[tuple(pdbs)] = case["name"]
    return mapping

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
        result = subprocess.run(["git", "-C", USALIGN_DIR, "checkout", branch],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] git checkout '{branch}' failed!"); sys.exit(1)
    else:
        print(f"  Already on '{branch}'")

def compile_usalign():
    env = os.environ.copy(); env["TMPDIR"] = "/tmp"
    result = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-std=gnu++11", "-fopenmp", "-static",
         "USalign.cpp", "UPGMA.cpp", "-o", "USalign_dir2_mm1", "-lm"],
        cwd=USALIGN_DIR, env=env, capture_output=True, text=True)
    if result.returncode != 0: print(f"[ERROR] Compilation failed:\n{result.stderr}"); sys.exit(1)
    print("  Compilation OK")

def run_usalign(work_dir, command, timeout=120):
    args = [USALIGN_EXE] + command
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=work_dir)
    return result.returncode, result.stdout, result.stderr

# ============================================================
# Step 2: Regression tests (per-comparison granularity)
# ============================================================
def run_regression_tests(cases):
    """Each format comparison counted separately. Returns (passed, warned, failed)."""
    print(f"\n[Step 2] Regression tests: {len(cases)} cases × 2 formats")
    print("-" * 60)
    passed, warned, failed = 0, 0, 0
    for case in cases:
        for outfmt in [2, -1]:
            fmt_str = "outfmt-1" if outfmt == -1 else f"outfmt{outfmt}"
            tag = f"{case['name']}_{fmt_str}"
            print(f"  {tag} ... ", end="", flush=True)

            baseline_file = os.path.join(BASELINE_DIR, f"{tag}.txt")
            result_file = os.path.join(RESULT_DIR, f"{tag}.txt")
            if not os.path.exists(baseline_file):
                print("SKIP (no baseline)"); continue

            full_cmd = case["command"] + ["-outfmt", str(outfmt)]
            if outfmt == -1: full_cmd.extend(["-m", "-"])

            rc, stdout, stderr = run_usalign(case["work_dir"], full_cmd)
            output = stdout + stderr
            if rc != 0 or "ERROR" in output:
                print(f"FAIL (execution error rc={rc})"); failed += 1; continue

            with open(result_file, "w", encoding="utf-8") as f:
                f.write(normalize_output(output))

            res = smart_compare(baseline_file, result_file, tag)
            if res == "PASS": passed += 1
            elif res == "WARNING": warned += 1
            else: failed += 1

    return passed, warned, failed

# ============================================================
# Step 3: Guard tests
# ============================================================
def run_guard_tests(guards):
    print(f"\n[Step 3] Guard tests: {len(guards)} cases")
    print("-" * 60)
    passed, warned, failed = 0, 0, 0
    for guard in guards:
        name = guard["name"]
        rc, stdout, stderr = run_usalign(guard["work_dir"], guard["command"])
        combined = stdout + stderr
        if rc == 0:
            print(f"  {name} FAIL (expected error exit, got rc=0)"); failed += 1; continue
        if guard["expect"] and guard["expect"] not in combined:
            print(f"  {name} FAIL (expected '{guard['expect']}' not found)"); failed += 1; continue
        print(f"  {name} PASS (rc={rc}, found '{guard['expect']}')"); passed += 1
    return passed, warned, failed

# ============================================================
# Step 4: Batch tests (Split & Cross-Validate, per-comparison)
# ============================================================
def run_batch_tests(batches, reg_map):
    """Each split comparison counted separately. Returns (passed, warned, failed)."""
    print(f"\n[Step 4] Batch tests: {len(batches)} cases (Split & Cross-Validate)")
    print("-" * 60)
    passed, warned, failed = 0, 0, 0

    for batch in batches:
        name = batch["name"]
        work_dir = batch["work_dir"]
        command = batch["command"]
        print(f"  {name}:")

        outfmt = 2
        for i, arg in enumerate(command):
            if arg == "-outfmt" and i + 1 < len(command):
                outfmt = int(command[i + 1])

        rc, stdout, stderr = run_usalign(work_dir, command, timeout=600)
        output = stdout + stderr
        if rc != 0 or "ERROR" in output:
            print(f"    FAIL (execution error rc={rc})"); failed += 1; continue

        # V7.1: Save Raw Batch Output
        raw_file = os.path.join(RESULT_DIR, f"{name}_raw.txt")
        norm_output = normalize_output(output)
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(norm_output)

        sp = sw = sf = 0  # split-level counters for this batch

        if outfmt == 2:
            # === Tabular format: header + data rows ===
            header = None; data_lines = []
            for line in norm_output.splitlines():
                stripped = line.strip()
                if not stripped: continue
                if stripped.startswith("#PDBchain1"):
                    header = line; continue
                if stripped.startswith("#"):
                    continue  # skip pairing-summary lines (new -mm 1 output)
                data_lines.append(line)

            if not header:
                print(f"    FAIL (no header found)"); failed += 1; continue

            for dline in data_lines:
                cols = dline.split()
                if len(cols) < 2:
                    print(f"    [WARN] Malformed data line, skipping"); sw += 1; continue

                pdb1_name = cols[0].split(":")[0]
                pdb2_name = cols[1].split(":")[0]
                pdb1_base = os.path.splitext(os.path.basename(pdb1_name))[0].lower()
                pdb2_base = os.path.splitext(os.path.basename(pdb2_name))[0].lower()
                pair_key = (pdb1_base, pdb2_base)

                if pair_key not in reg_map:
                    print(f"    [WARN] Pair {pair_key} not found in regression cases!")
                    sw += 1; continue

                reg_name = reg_map[pair_key]
                split_tag = f"split_{reg_name}_outfmt2"
                split_file = os.path.join(RESULT_DIR, f"{split_tag}.txt")
                with open(split_file, "w", encoding="utf-8") as f:
                    f.write(header + "\n" + dline + "\n")

                baseline_file = os.path.join(BASELINE_DIR, f"{reg_name}_outfmt2.txt")
                print(f"    {split_tag} ... ", end="", flush=True)
                res = smart_compare(baseline_file, split_file, split_tag)
                if res == "PASS": sp += 1
                elif res == "WARNING": sw += 1
                else: sf += 1

        elif outfmt == -1:
            # === Detailed format: split by "Name of Structure_1:" blocks ===
            lines = norm_output.splitlines()
            blocks = []
            current_block = []
            started = False
            for line in lines:
                if line.startswith("Name of Structure_1:"):
                    if started and current_block:
                        blocks.append(current_block)
                    current_block = [line]
                    started = True
                else:
                    if started and not line.strip().startswith("#"):
                        current_block.append(line)
            if started and current_block:
                while current_block and is_non_business_line(current_block[-1]):
                    current_block.pop()
                if current_block:
                    blocks.append(current_block)

            for block in blocks:
                pdb1 = pdb2 = None
                for bline in block:
                    m1 = re.search(r'Name of Structure_1:\s+([\w.\-]+\.\w+):', bline)
                    m2 = re.search(r'Name of Structure_2:\s+([\w.\-]+\.\w+):', bline)
                    if m1: pdb1 = m1.group(1)
                    if m2: pdb2 = m2.group(1)

                if not pdb1 or not pdb2:
                    print(f"    [WARN] Could not extract PDB names from block ({len(block)} lines)")
                    sw += 1; continue

                pdb1_base = os.path.splitext(os.path.basename(pdb1))[0].lower()
                pdb2_base = os.path.splitext(os.path.basename(pdb2))[0].lower()
                pair_key = (pdb1_base, pdb2_base)

                if pair_key not in reg_map:
                    print(f"    [WARN] Pair {pair_key} not found in regression cases!")
                    sw += 1; continue

                reg_name = reg_map[pair_key]
                split_tag = f"split_{reg_name}_outfmt-1"
                split_file = os.path.join(RESULT_DIR, f"{split_tag}.txt")
                with open(split_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(block) + "\n")

                baseline_file = os.path.join(BASELINE_DIR, f"{reg_name}_outfmt-1.txt")
                print(f"    {split_tag} ... ", end="", flush=True)
                res = smart_compare(baseline_file, split_file, split_tag)
                if res == "PASS": sp += 1
                elif res == "WARNING": sw += 1
                else: sf += 1

        passed += sp; warned += sw; failed += sf
        print(f"    => Splits: {sp} passed, {sw} warned, {sf} failed")

    return passed, warned, failed

# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Test runner for -dir2 + -mm 1 (V7.1)")
    parser.add_argument("--branch", default="USalign-beta", help="Target branch to test")
    args = parser.parse_args()

    print("=" * 60)
    print("Test Runner: -dir2 + -mm 1 (V7.1)")
    print("=" * 60)

    regression_cases = read_regression_cases()
    guards, batches = read_feature_cases()
    reg_map = build_regression_map(regression_cases)

    print(f"\nRegression cases: {len(regression_cases)}")
    print(f"Guard cases: {len(guards)}")
    print(f"Batch cases: {len(batches)}")

    if not os.path.exists(BASELINE_DIR):
        print(f"\n[ERROR] Baseline directory not found: {BASELINE_DIR}")
        print(f"Run generate_dir2_mm1_baseline.py first!"); sys.exit(1)

    # V7.1: Clean historical result/diff before each run
    print(f"\n[Step 0] Cleaning historical results & diffs")
    clean_result_dirs()

    original_branch = current_branch()
    try:
        print(f"\n[Step 1] Checkout '{args.branch}' & compile")
        git_checkout(args.branch)
        compile_usalign()

        reg_pass, reg_warn, reg_fail = run_regression_tests(regression_cases)
        guard_pass, guard_warn, guard_fail = run_guard_tests(guards)
        batch_pass, batch_warn, batch_fail = run_batch_tests(batches, reg_map)

    finally:
        if original_branch and original_branch != current_branch():
            print(f"[Restore] Switching USalign back to '{original_branch}'")
            git_checkout(original_branch)

    # V7.1: All per-comparison, numbers add up directly
    total_pass = reg_pass + guard_pass + batch_pass
    total_warn = reg_warn + guard_warn + batch_warn
    total_fail = reg_fail + guard_fail + batch_fail

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Regression: {reg_pass} passed, {reg_warn} warned, {reg_fail} failed")
    print(f"  Guard:      {guard_pass} passed, {guard_warn} warned, {guard_fail} failed")
    print(f"  Batch:      {batch_pass} passed, {batch_warn} warned, {batch_fail} failed")
    print(f"  -------------------------------------")
    print(f"  Total:      {total_pass} passed, {total_warn} warned, {total_fail} failed")

    if total_fail > 0: print("\n[FAIL] TESTS FAILED"); sys.exit(1)
    elif total_warn > 0: print("\n[WARN] TESTS PASSED WITH WARNINGS"); sys.exit(0)
    else: print("\n[PASS] ALL TESTS STRICTLY PASSED"); sys.exit(0)

if __name__ == "__main__":
    main()

