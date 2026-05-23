#!/usr/bin/env python3
"""
Generate baseline data for -dir + -mm 1 tests.
Runs on master branch, always overwrites existing baselines.
NOTE: Master branch does NOT support -dir -mm 1, so we ONLY generate single-pair baselines.

Usage:
    cd USalign-master && python3 test/scripts/generate_dir_mm1_baseline.py
"""

import os
import subprocess
import sys
import re

# --- paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_DIR = os.path.dirname(TEST_DIR)
USALIGN_DIR = os.path.join(PROJECT_DIR, "USalign")

USALIGN_EXE = os.path.join(USALIGN_DIR, "USalign_dir_mm1.exe" if sys.platform == "win32" else "USalign_dir_mm1")
TEST_CASES_FILE = os.path.join(SCRIPT_DIR, "dir_mm1_test_cases.txt")
BASELINE_DIR = os.path.join(SCRIPT_DIR, "dirbaseline")


def normalize_path_in_line(line):
    """Strip ALL directory prefixes from PDB paths, keep only filename.pdb:"""
    line = re.sub(r'[A-Za-z]:[/\\]', '', line)
    line = re.sub(r'(?:[\w.\-]+[/\\])+([\w.\-]+\.pdb:)', r'\1', line)
    line = re.sub(r'[/\\]([\w.\-]+\.pdb:)', r'\1', line)
    return line

def normalize_output(text):
    """Normalize all paths in USalign output text before writing to file."""
    lines = text.splitlines()
    result = []
    for line in lines:
        line = line.replace("\\", "/")
        line = normalize_path_in_line(line)
        result.append(line)
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(result) + trailing

def write_normalized(filepath, text):
    """Write output to file after normalizing paths."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(normalize_output(text))

def read_test_cases():
    if not os.path.exists(TEST_CASES_FILE):
        print(f"[ERROR] Test cases file not found: {TEST_CASES_FILE}")
        sys.exit(1)
    cases = []
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            name, rel_dir, command = parts[0], parts[1], parts[2:]
            work_dir = os.path.join(PROJECT_DIR, rel_dir) if rel_dir != "." else PROJECT_DIR
            cases.append((name, work_dir, command))
    return cases

def git_checkout(branch):
    """Checkout the specified branch in USalign source directory."""
    result = subprocess.run(
        ["git", "-C", USALIGN_DIR, "branch", "--show-current"],
        capture_output=True, text=True
    )
    current = result.stdout.strip()
    if current != branch:
        print(f"  Switching from '{current}' to '{branch}'...")
        result = subprocess.run(
            ["git", "-C", USALIGN_DIR, "checkout", branch],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[ERROR] git checkout '{branch}' failed!")
            print(f"  stderr: {result.stderr.strip()}")
            sys.exit(1)
    else:
        print(f"  Already on '{branch}'")

def compile_usalign():
    """Compile USalign (always recompile)."""
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

def run_single_pair(work_dir, command, outfmt):
    args = [USALIGN_EXE] + command + ["-outfmt", str(outfmt)]
    if outfmt == -1:
        args.extend(["-m", "-"])
    result = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=work_dir)
    output = result.stdout + result.stderr
    ok = result.returncode == 0 and "ERROR" not in output
    return output, ok

def main():
    print("=" * 60)
    print("Generate Baseline: -dir + -mm 1 (Single-Pair ONLY)")
    print("=" * 60)
    cases = read_test_cases()
    print(f"\nTest cases: {len(cases)} entries")
    for name, _, cmd in cases:
        print(f"  {name}: {' '.join(cmd)}")

    # Step 1: Checkout master & compile
    print(f"\n[Step 1] Checkout master & compile")
    git_checkout("master")
    compile_usalign()

    os.makedirs(BASELINE_DIR, exist_ok=True)

    # Step 2: Generate single-pair baselines (always overwrite)
    print(f"\n[Step 2] Generating single-pair baselines")
    for name, work_dir, command in cases:
        for outfmt in [2, -1]:
            fmt_str = "outfmt-1" if outfmt == -1 else f"outfmt{outfmt}"
            baseline_file = os.path.join(BASELINE_DIR, f"{name}_{fmt_str}.txt")
            print(f"  {name} [{fmt_str}] ... ", end="", flush=True)
            output, ok = run_single_pair(work_dir, command, outfmt)
            if not ok:
                print("FAILED")
                sys.exit(1)
            write_normalized(baseline_file, output)
            print("OK")

    # Step 3: Verify no directory prefixes left
    print(f"\n[Step 3] Verifying baseline files")
    bad = 0
    for fname in sorted(os.listdir(BASELINE_DIR)):
        if not fname.endswith(".txt"): continue
        fpath = os.path.join(BASELINE_DIR, fname)
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if re.search(r'[/\\][\w.\-]+\.pdb:', line) or \
                   re.search(r'[A-Za-z]:[/\\]', line):
                    print(f"  WARNING: {fname} still has directory prefix!")
                    bad += 1
                    break
    if bad == 0:
        print("  All baseline files are clean (no directory prefixes)")
    else:
        print(f"  {bad} file(s) still have directory prefixes!")

    print(f"\n[DONE] Baselines saved to: {BASELINE_DIR}")

if __name__ == "__main__":
    sys.exit(main())
