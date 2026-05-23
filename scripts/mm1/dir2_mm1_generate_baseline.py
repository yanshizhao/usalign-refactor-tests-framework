#!/usr/bin/env python3
"""
Generate baseline data for -dir2 + -mm 1 tests. (V7.1 Compliant)
Runs on master branch. Only generates single-pair baselines.
Batch tests use split cross-validation against single-pair baselines.
"""
import os
import subprocess
import sys
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_DIR = os.path.dirname(TEST_FRAMEWORK_DIR)
USALIGN_DIR = os.path.join(PROJECT_DIR, "USalign")
USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_dir2_mm1.exe" if sys.platform == "win32" else "USalign_dir2_mm1")
TEST_CASES_FILE = os.path.join(SCRIPT_DIR, "dir2_mm1_test_cases.txt")
BASELINE_DIR = os.path.join(SCRIPT_DIR, "dir2baseline")

# ============================================================
# Utility functions
# ============================================================
def normalize_path_in_line(line):
    """Strip ALL directory prefixes from file paths, keep only filename.ext:"""
    line = re.sub(r'[A-Za-z]:[/\\]', '', line)
    # V7.1: Must cover ALL extensions, not just .pdb
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

def write_normalized(filepath, text):
    """Write output to file after normalizing paths only."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(normalize_output(text))

# ============================================================
# Test case parsing
# ============================================================
def read_test_cases():
    cases = []
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split()
            if len(parts) < 3: continue
            name, rel_dir, command = parts[0], parts[1], parts[2:]
            work_dir = os.path.join(PROJECT_DIR, rel_dir) if rel_dir != "." else PROJECT_DIR
            cases.append((name, work_dir, command))
    return cases

# ============================================================
# Build & branch
# ============================================================
def git_checkout(branch):
    result = subprocess.run(["git", "-C", USALIGN_DIR, "branch", "--show-current"], capture_output=True, text=True)
    current = result.stdout.strip()
    if current != branch:
        print(f"  Switching from '{current}' to '{branch}'...")
        result = subprocess.run(["git", "-C", USALIGN_DIR, "checkout", branch], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] git checkout '{branch}' failed!"); sys.exit(1)
    else:
        print(f"  Already on '{branch}'")

def compile_usalign():
    env = os.environ.copy(); env["TMPDIR"] = "/tmp"
    result = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-static", "USalign.cpp", "-o", "USalign_dir2_mm1", "-lm"],
        cwd=USALIGN_DIR, env=env, capture_output=True, text=True)
    if result.returncode != 0: print(f"[ERROR] Compilation failed:\n{result.stderr}"); sys.exit(1)
    print("  Compilation OK")

# ============================================================
# Run
# ============================================================
def run_single_pair(work_dir, command, outfmt):
    args = [USALIGN_EXE] + command + ["-outfmt", str(outfmt)]
    if outfmt == -1: args.extend(["-m", "-"])
    result = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=work_dir)
    output = result.stdout + result.stderr
    ok = result.returncode == 0 and "ERROR" not in output
    return output, ok

# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Generate Baseline: -dir2 + -mm 1 (Single-Pair Only)")
    print("=" * 60)

    cases = read_test_cases()
    print(f"\nTest cases: {len(cases)} entries")
    for name, _, cmd in cases:
        print(f"  {name}: {' '.join(cmd)}")

    print(f"\n[Step 1] Checkout master & compile")
    git_checkout("master")
    compile_usalign()
    os.makedirs(BASELINE_DIR, exist_ok=True)

    print(f"\n[Step 2] Generating single-pair baselines (outfmt 2 & -1)")
    for name, work_dir, command in cases:
        for outfmt in [2, -1]:
            fmt_str = "outfmt-1" if outfmt == -1 else f"outfmt{outfmt}"
            baseline_file = os.path.join(BASELINE_DIR, f"{name}_{fmt_str}.txt")
            print(f"  {name} [{fmt_str}] ... ", end="", flush=True)
            output, ok = run_single_pair(work_dir, command, outfmt)
            if not ok: print("FAILED"); sys.exit(1)
            write_normalized(baseline_file, output)
            print("OK")

    print(f"\n[Step 3] Verifying baseline files (checking for residual directory prefixes)")
    bad = 0
    for fname in sorted(os.listdir(BASELINE_DIR)):
        if not fname.endswith(".txt"): continue
        with open(os.path.join(BASELINE_DIR, fname), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if re.search(r'[/\\][\w.\-]+\.\w+:', line) or re.search(r'[A-Za-z]:[/\\]', line):
                    print(f"  WARNING: {fname} still has directory prefix!"); bad += 1; break
    if bad == 0: print("  All clean!")
    else: print(f"  {bad} file(s) still have directory prefixes!")

    print(f"\n[DONE] Single-pair baselines saved to: {BASELINE_DIR}")
    print("[NOTE] No batch baselines needed. Batch tests use split cross-validation.")

if __name__ == "__main__":
    main()
