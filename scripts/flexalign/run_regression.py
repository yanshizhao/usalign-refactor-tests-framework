#!/usr/bin/env python3
"""
Regression test runner for -mm 7 (flexible alignment).
Compares outputs between master (baseline) and USalign-beta (current) branches.
"""
import subprocess
import os
import sys
import shutil
import re
import difflib
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
CURRENT = SCRIPT_DIR / "current"
BASELINE = SCRIPT_DIR / "baseline"
DIFFS = SCRIPT_DIR / "diffs"

USALIGN_DIR = Path("/d/qlab/us-align_modify/USalign").resolve()
SRC = [USALIGN_DIR / "USalign.cpp", USALIGN_DIR / "UPGMA.cpp"]

EXE_SUFFIX = ".exe" if os.name == "nt" else ""
EXE_MASTER = SCRIPT_DIR / f"USalign_orig{EXE_SUFFIX}"
EXE_BETA   = SCRIPT_DIR / f"USalign_mod{EXE_SUFFIX}"

MASTER_BRANCH = "master"
BETA_BRANCH   = "USalign-beta"


def current_branch():
    try:
        r = subprocess.run(["git", "branch", "--show-current"],
                           cwd=str(USALIGN_DIR), capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def checkout(branch):
    r = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Failed to checkout {branch}: {r.stderr}")
        sys.exit(1)


def compile_exe(branch, exe_path):
    """Compile USalign from the specified branch to exe_path."""
    print(f"Compiling USalign from {branch} branch...")
    checkout(branch)
    # Use the same compilation command as readme.txt for consistency
    cmd = ["g++", "-O3", "-ffast-math", "-std=gnu++11", "-fopenmp",
           "-o", str(exe_path)] + [str(s) for s in SRC]
    if os.name == "nt":
        # Windows: use static linking
        cmd.insert(4, "-static")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("Compilation failed!"); sys.exit(1)
    print(f"  -> {exe_path}")


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (same as cLanguage2Cplus)."""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def strip_cpu_time(text: str) -> str:
    """Remove CPU time lines (non-deterministic)."""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def clean_output(text: str) -> str:
    """Apply all cleaning steps for comparison."""
    text = clean_slash(text)
    text = strip_cpu_time(text)
    return text


def run_case(exe, workdir, args_list):
    """Run one test case and return cleaned stdout+stderr."""
    # Inject -threads 1 for deterministic floating-point output
    cmd = [str(exe)] + args_list + ["-threads", "1"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
    return clean_output(proc.stdout + proc.stderr)


def main():
    original = current_branch()
    try:
        # Step 1: Compile master (baseline)
        compile_exe(MASTER_BRANCH, EXE_MASTER)

        # Step 2: Compile beta (current)
        compile_exe(BETA_BRANCH, EXE_BETA)

        # Step 3: Clean output dirs
        for d in [CURRENT, DIFFS]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)

        # Step 4: Read test cases
        cases_file = SCRIPT_DIR / "testcases_functional.txt"
        if not cases_file.exists():
            print(f"Test cases file not found: {cases_file}"); sys.exit(1)

        with open(cases_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total = passed = warned = failed = 0

        # Ensure baseline directory exists (may already have baselines from create_baseline.py)
        BASELINE.mkdir(parents=True, exist_ok=True)

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            name, workdir_rel, args_str = parts
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split()

            print(f"\n=== {name} ===")

            # Run with master (baseline)
            base_text = run_case(EXE_MASTER, workdir, args_list)
            base_file = BASELINE / f"{name}.out"
            with open(base_file, "w", encoding="utf-8") as of:
                of.write(base_text)

            # Run with beta (current)
            cur_text = run_case(EXE_BETA, workdir, args_list)
            cur_file = CURRENT / f"{name}.out"
            with open(cur_file, "w", encoding="utf-8") as of:
                of.write(cur_text)

            # Compare
            if base_text == cur_text:
                print(f"  PASS")
                passed += 1
            else:
                # Generate unified diff
                base_lines = base_text.splitlines()
                cur_lines = cur_text.splitlines()
                diff = list(difflib.unified_diff(
                    base_lines, cur_lines,
                    fromfile=f"baseline/{name}.out",
                    tofile=f"current/{name}.out",
                    lineterm=""
                ))
                # Filter out non-business lines (CPU time, blank)
                business_diff = [l for l in diff
                                 if (l.startswith("+") or l.startswith("-"))
                                 and not l.startswith(("+++", "---"))
                                 and not l.strip().startswith("#Total CPU time")
                                 and l.strip() not in ("+", "-")]

                if not business_diff:
                    print(f"  WARNING (only CPU time / formatting differences)")
                    warned += 1
                else:
                    print(f"  FAIL - business output differs")
                    failed += 1

                # Write diff file
                diffs_file = DIFFS / f"{name}.diff"
                with open(diffs_file, "w", encoding="utf-8") as df:
                    df.write("\n".join(diff) + "\n")
                if business_diff:
                    print(f"  Diff -> {diffs_file}")
                    # Print first few diff lines for quick inspection
                    for dl in business_diff[:10]:
                        print(f"    {dl}")

            total += 1

        print(f"\n===== Summary: total={total}, PASS={passed}, WARNING={warned}, FAIL={failed} =====")
        return 0 if failed == 0 else 1

    finally:
        if original and original != BETA_BRANCH:
            print(f"Restoring branch to {original}...")
            checkout(original)


if __name__ == "__main__":
    sys.exit(main())
