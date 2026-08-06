#!/usr/bin/env python3
import subprocess, os, shutil, sys, re, platform
from pathlib import Path

"""
Baseline creator for -chainmap local-constraint tests.
Follows the cLanguage2Cplus framework pattern:
  1. Switch USalign repo to the master branch, compile USalign_chainmap_orig.exe
  2. Run regression cases (testcases_regression.txt) with the master executable
  3. Save cleaned outputs to baseline/ as the golden standard
  4. Restore the original branch (USalign-beta)

Note: run this BEFORE implementing the 15 chainmap code changes.
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
BASELINE = SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
# master branch has no UPGMA.cpp (added later on USalign-beta); compile USalign.cpp only
SRC = [USALIGN_DIR / "USalign.cpp"]

EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = SCRIPT_DIR / f"USalign_chainmap_orig{EXE_SUFFIX}"


def current_branch():
    r = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("Failed to get current branch:", r.stderr); sys.exit(1)
    return r.stdout.strip()


def checkout(branch):
    r = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Failed to checkout {branch}:\n{r.stderr}"); sys.exit(1)


def compile_exe():
    print("Compiling baseline US-align from master...")
    cmd = ["g++", "-O3", "-ffast-math", "-fopenmp", "-o", str(EXE)] + [str(s) for s in SRC]
    if platform.system() == "Windows":
        cmd.insert(4, "-static-libgcc")
        cmd.insert(5, "-static-libstdc++")
    if subprocess.run(cmd).returncode != 0:
        print("Compilation failed!"); sys.exit(1)
    print("Baseline executable:", EXE)


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (keep master/beta output comparable)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def run_baseline():
    if BASELINE.exists():
        shutil.rmtree(BASELINE, ignore_errors=True)
    BASELINE.mkdir(parents=True)

    with open(SCRIPT_DIR / "testcases_regression.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            cmd = [str(EXE)] + args_str.split()
            print(f"=== {name} ===")
            print(f"  CMD: {' '.join(cmd)}")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = clean_slash(proc.stdout + proc.stderr)
            with open(BASELINE / f"{name}.out", "w", encoding="utf-8") as out:
                out.write(content)
    print("\nBaseline created.")


if __name__ == "__main__":
    original = current_branch()
    try:
        if original != "master":
            print(f"Switching USalign {original} -> master for baseline...")
            checkout("master")
        compile_exe()
        run_baseline()
    finally:
        if original and original != "master":
            print(f"Restoring USalign branch to {original}...")
            checkout(original)
