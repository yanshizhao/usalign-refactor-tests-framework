#!/usr/bin/env python3
"""
Create baseline outputs for flexalign regression tests.
Compiles USalign from the master branch (golden baseline) and runs
all test cases, saving cleaned outputs to baseline/.
"""
import subprocess
import os
import sys
import shutil
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
BASELINE = SCRIPT_DIR / "baseline"

# Use the USalign directory within the current workspace
# __file__ = .../usalign-refactor-tests-framework/scripts/flexalign/create_baseline.py
# parent.parent.parent.parent = us-align_modify/
USALIGN_DIR = Path(__file__).parent.parent.parent.parent / "USalign"

# Verify the directory exists
if not USALIGN_DIR.exists():
    print(f"Error: USALIGN_DIR does not exist: {USALIGN_DIR}")
    sys.exit(1)

# Build compilation sources based on branch
SRC_MASTER = [str(USALIGN_DIR / "USalign.cpp")]
SRC_BETA = [str(USALIGN_DIR / "USalign.cpp"), str(USALIGN_DIR / "UPGMA.cpp")]

EXE_SUFFIX = ".exe" if os.name == "nt" else ""
EXE = SCRIPT_DIR / f"USalign_orig{EXE_SUFFIX}"


def current_branch():
    try:
        # Use git -C to specify working directory
        r = subprocess.run(["git", "-C", str(USALIGN_DIR), "branch", "--show-current"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def checkout(branch):
    r = subprocess.run(["git", "-C", str(USALIGN_DIR), "checkout", branch],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Failed to checkout {branch}: {r.stderr}")
        sys.exit(1)


def compile_exe(branch):
    """Compile USalign from the specified branch for baseline."""
    print(f"Compiling USalign from {branch} branch for baseline...")
    checkout(branch)
    # Use compilation command matching the branch's readme.txt
    if branch == "master":
        # Master readme.txt: g++ -static -O3 -ffast-math -lm -o USalign USalign.cpp
        cmd = ["g++", "-O3", "-ffast-math", "-static", "-lm", "-o", str(EXE)]
        cmd.extend(SRC_MASTER)
    else:
        # Beta readme.txt: g++ -static -O3 -ffast-math -std=gnu++11 -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp
        cmd = ["g++", "-O3", "-ffast-math", "-std=gnu++11", "-fopenmp",
               "-static", "-lm", "-o", str(EXE)]
        cmd.extend(SRC_BETA)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("Compilation failed!"); sys.exit(1)
    print(f"Baseline executable: {EXE}")


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (same as cLanguage2Cplus)."""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def strip_cpu_time(text: str) -> str:
    """Remove CPU time lines (non-deterministic)."""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def main():
    original = current_branch()
    try:
        compile_exe("master")

        # Clean and create baseline directory
        if BASELINE.exists():
            shutil.rmtree(BASELINE, ignore_errors=True)
        BASELINE.mkdir(parents=True, exist_ok=True)

        cases_file = SCRIPT_DIR / "testcases_functional.txt"
        with open(cases_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        case_count = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            name, workdir_rel, args_str = parts
            workdir = (DATA_DIR / workdir_rel).resolve()
            # Note: Master branch does NOT support -threads, so no injection
            args_list = args_str.split()
            cmd = [str(EXE)] + args_list

            print(f"=== {name} ===")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = clean_slash(proc.stdout + proc.stderr)

            out_file = BASELINE / f"{name}.out"
            with open(out_file, "w", encoding="utf-8") as of:
                of.write(content)
            print(f"  Saved baseline -> {out_file}")
            case_count += 1

        print(f"\nBaseline created: {case_count} cases")
    finally:
        if original and original != "master":
            print(f"Restoring branch to {original}...")
            checkout(original)


if __name__ == "__main__":
    main()