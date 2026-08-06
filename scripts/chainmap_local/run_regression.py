#!/usr/bin/env python3
import subprocess, os, sys, shutil, difflib, re, platform
from pathlib import Path

"""
Regression runner for -chainmap local-constraint tests.
Follows the cLanguage2Cplus framework pattern:
  1. Compile USalign-beta (+ chainmap changes) to USalign_chainmap_new.exe
  2. Run regression cases (testcases_regression.txt) -> current/*.out
  3. Diff against baseline/*.out (strip CPU time; ignore non-business lines)
  4. Report PASS / WARNING (CPU time only) / FAIL per case

Usage:
    python run_regression.py
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
CURRENT = SCRIPT_DIR / "current"
DIFFS = SCRIPT_DIR / "diffs"
BASELINE = SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = [USALIGN_DIR / "USalign.cpp", USALIGN_DIR / "UPGMA.cpp"]

EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = SCRIPT_DIR / f"USalign_chainmap_new{EXE_SUFFIX}"

# Tested code must be compiled from the USalign-beta branch (all changes live there)
TARGET_BRANCH = "USalign-beta"


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
    print("Compiling USalign-beta (+ chainmap changes)...")
    cmd = ["g++", "-O3", "-ffast-math", "-fopenmp", "-o", str(EXE)] + [str(s) for s in SRC]
    if platform.system() == "Windows":
        cmd.insert(4, "-static-libgcc")
        cmd.insert(5, "-static-libstdc++")
    if subprocess.run(cmd).returncode != 0:
        print("Compilation failed!"); sys.exit(1)
    print("Test executable:", EXE)


def clean_directory(dir_path):
    if dir_path.exists():
        shutil.rmtree(dir_path, ignore_errors=True)
    dir_path.mkdir(parents=True, exist_ok=True)


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (same as baseline creator)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def strip_cpu_time(text: str) -> str:
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def is_non_business_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if "#Total CPU time is" in stripped:
        return True
    return False


def run_tests():
    clean_directory(CURRENT)
    clean_directory(DIFFS)

    total, passed, warned, failed = 0, 0, 0, 0
    with open(SCRIPT_DIR / "testcases_regression.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            cmd = [str(EXE)] + args_str.split()
            print(f"=== {name} ===")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = clean_slash(proc.stdout + proc.stderr)
            with open(CURRENT / f"{name}.out", "w", encoding="utf-8") as out:
                out.write(content)

            base_file = BASELINE / f"{name}.out"
            if not base_file.exists():
                print("  FAIL: baseline missing")
                failed += 1; total += 1
                continue

            base_text = strip_cpu_time(base_file.read_text(encoding="utf-8"))
            cur_text = strip_cpu_time(content)
            if base_text == cur_text:
                print("  PASS: identical to baseline")
                passed += 1
            else:
                diff_lines = list(difflib.unified_diff(
                    base_text.splitlines(), cur_text.splitlines(),
                    fromfile=f"baseline/{name}.out", tofile=f"current/{name}.out", lineterm=""))
                business_diff = [l for l in diff_lines
                                 if (l.startswith("+") or l.startswith("-"))
                                 and not l.startswith(("+++", "---"))
                                 and not is_non_business_line(l)]
                if business_diff:
                    print("  FAIL: business output differs")
                    failed += 1
                else:
                    print("  WARNING: only CPU time / blank lines differ")
                    warned += 1
                (DIFFS / f"{name}.diff").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
            total += 1

    print(f"\n===== Regression summary: {passed} passed, {warned} warning, {failed} failed "
          f"(total {total}) =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    original = current_branch()
    try:
        # regression tests MUST run against the USalign-beta branch
        if original != TARGET_BRANCH:
            print(f"Switching USalign {original} -> {TARGET_BRANCH} for regression...")
            checkout(TARGET_BRANCH)
        compile_exe()
        sys.exit(run_tests())
    finally:
        if original and original != TARGET_BRANCH:
            print(f"Restoring USalign branch to {original}...")
            checkout(original)
