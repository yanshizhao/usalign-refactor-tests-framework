#!/usr/bin/env python3
import subprocess, os, sys, re
from pathlib import Path

"""
Performance baseline creation script (Performance Baseline Creator)
Features:
  1. Switch to the clean master branch, compile the original (unmodified) US-align executable
  2. Read all performance test cases from testcases_performance.txt
  3. Run each case multiple times (default 5), extracting #Total CPU time from each run
  4. Calculate the average time (seconds) for each case and save to perf_baseline/baseline.csv
  5. Print command-line debugging info (CWD, CMD), and output warnings and program tail on extraction failure
  6. Automatically handle -dir/-dir2 path conversion to ensure list files can be found correctly
Note: This script should be run once before modifying the source code to establish a performance reference baseline.
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"
# POSIX shell does not include PWD in PATH
EXE = os.path.abspath("USalign_orig.exe")
PERF_DIR = SCRIPT_DIR / "perf_baseline"
RUNS = 5


def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def compile():
    print("Compiling original US-align from master...")
    if subprocess.run(["g++", "-O3", "-lm", "-static", "-o", EXE, str(SRC)]).returncode != 0:
        print("Compilation failed!"); sys.exit(1)

def extract_time(output: str) -> float:
    m = re.search(r"#Total CPU time\s+is\s+([\d\.]+)\s+seconds", output)
    return float(m.group(1)) if m else 0.0

def run_benchmarks():
    if not PERF_DIR.exists(): PERF_DIR.mkdir(parents=True)
    with open(PERF_DIR / "baseline.csv", "w", newline='') as csv:
        csv.write("case,avg_time\n")
        with open("testcases_performance.txt", "r", encoding="utf-8") as tf:
            for line in tf:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, workdir_rel, args_str = line.split(maxsplit=2)
                workdir = (DATA_DIR / workdir_rel).resolve()
                args_list = args_str.split()
                cmd = [EXE] + args_list
                print(f"Benchmarking {name} (baseline)...")
                print(f"  CWD: {workdir}")
                print(f"  CMD: {' '.join(cmd)}")
                total = 0.0
                for run_idx in range(RUNS):
                    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
                    t = extract_time(proc.stdout + proc.stderr)
                    if t == 0.0:
                        print(f"  Warning: run {run_idx+1} failed to extract time.")
                    total += t
                avg = round(total / RUNS, 3)
                csv.write(f"{name},{avg}\n")
    print("Performance baseline saved.")

if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for performance baseline...")
            checkout("master")
        compile()
        run_benchmarks()
    finally:
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
