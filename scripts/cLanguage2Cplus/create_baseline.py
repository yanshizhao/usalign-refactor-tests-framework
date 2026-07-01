#!/usr/bin/env python3
import subprocess, os, shutil, sys, re, platform
from pathlib import Path

"""
Baseline file creation script (Baseline Creator)
Features:
  1. Switch to the clean master branch, compile the original (unmodified) US-align executable (USalign_orig.exe)
  2. Read all functional test cases from testcases_functional.txt
  3. Execute each case sequentially, saving the full output (stdout and stderr) to
     the baseline/ directory as the "golden standard" for subsequent regression tests
  4. Automatically set the correct working directory for each case, ensuring all structure files can be found
  5. For cases with -dir/-dir2 options, automatically convert list file paths to absolute paths
  6. Print "Baseline created." prompt after completion
Note: This script should be run only once before modifying the source code, to establish immutable expected output.
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
BASELINE = SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"

# Cross-platform executable: add .exe only on Windows
EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = os.path.abspath(f"USalign_orig{EXE_SUFFIX}")


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
    compile_cmd = ["g++", "-O3", "-ffast-math", "-o", EXE, str(SRC)]
    if platform.system() == "Windows":
        compile_cmd.insert(3, "-static-libgcc")
        compile_cmd.insert(4, "-static-libstdc++")
    if subprocess.run(compile_cmd).returncode != 0:
        print("Compilation failed!"); sys.exit(1)


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (both 'Name of Structure_X:' and table columns)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def run_baseline():
    if not BASELINE.exists():
        BASELINE.mkdir(parents=True)
    with open("testcases_functional.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split()
            cmd = [EXE] + args_list
            print(f"=== {name} ===")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            # Capture output, clean it, then write to baseline file
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr
            content = clean_slash(content)

            out_file = BASELINE / f"{name}.out"
            with open(out_file, "w", encoding="utf-8") as out:
                out.write(content)

            if name == "superposed_structure":
                sup_pdb = workdir / "sup.pdb"
                if sup_pdb.exists():
                    shutil.move(str(sup_pdb), str(BASELINE / "sup.pdb"))
    print("\nBaseline created.")


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for functional baseline...")
            checkout("master")
        compile()
        run_baseline()
    finally:
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
