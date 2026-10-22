#!/usr/bin/env python3
"""
addChainID baseline creation script
Switch to the clean master branch, extract unmodified source code, compile the
original addChainID, run all test cases, and save output to baseline/.
master has no -outdir option, so testcases_baseline.txt is used here while
run_test.py appends "-outdir ." to the same arguments.
Besides stdout/stderr, the file written by each case (out.pdb) is saved as a
separate artifact. Restores the branch that was active before running.
"""
import subprocess, os, shutil, sys, tempfile, platform
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
SRC_MAIN     = "addChainID.cpp"
EXE_NAME     = "addChainID_orig.exe"
ARTIFACTS    = ["out.pdb"]


def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def extract_master_sources(tmpdir: str):
    """Extract all .cpp and .h source files from the master branch to a temporary directory"""
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "-r", "master"],
        capture_output=True, text=True, cwd=str(USALIGN_DIR)
    )
    if result.returncode != 0:
        print("ERROR: cannot list master branch"); sys.exit(1)

    for fname in result.stdout.strip().split("\n"):
        if not fname.endswith((".cpp", ".h")):
            continue
        content = subprocess.run(
            ["git", "show", f"master:{fname}"],
            capture_output=True, text=True, cwd=str(USALIGN_DIR)
        )
        if content.returncode != 0:
            print(f"WARNING: skip {fname}")
            continue
        dst = os.path.join(tmpdir, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content.stdout)


def compile_orig(exe_path: str, tmpdir: str):
    print("Compiling original addChainID from master ...")
    src = os.path.join(tmpdir, SRC_MAIN)
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static", "-I", tmpdir, "-o", exe_path, src],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def normalize(text: str, exe_path: str) -> str:
    """Replace the executable path, which legitimately differs between runs"""
    return text.replace(str(exe_path), "EXE")


def needs_gzip(args) -> bool:
    """Compressed input is read through pstream.h, which is POSIX-only
    (it defines NO_PSTREAM on Windows), so .gz cases can only run on POSIX."""
    return any(a.endswith((".gz", ".bz2")) for a in args)


def run_baseline(exe_path: str):
    if BASELINE_DIR.exists():
        shutil.rmtree(BASELINE_DIR)
    BASELINE_DIR.mkdir(parents=True)

    testcases = SCRIPT_DIR / "testcases_baseline.txt"
    with open(testcases, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args = args_str.split()
            cmd = [exe_path] + args

            if platform.system() == "Windows" and needs_gzip(args):
                print(f"=== {name} === SKIP (compressed input unsupported on Windows)")
                continue

            print(f"=== {name} ===")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            for artifact in ARTIFACTS:
                stale = workdir / artifact
                if stale.exists():
                    stale.unlink()

            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = normalize(proc.stdout + proc.stderr, exe_path)
            (BASELINE_DIR / f"{name}.out").write_text(content, encoding="utf-8")

            for artifact in ARTIFACTS:
                path = workdir / artifact
                if path.exists():
                    shutil.move(str(path), str(BASELINE_DIR / f"{name}.{Path(artifact).suffix[1:]}"))

    print("\naddChainID baseline created.")


if __name__ == "__main__":
    original_branch = current_branch()
    tmpdir = tempfile.mkdtemp(prefix="addchainid_orig_")
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for addChainID baseline...")
            checkout("master")
        extract_master_sources(tmpdir)
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_orig(exe, tmpdir)
        run_baseline(exe)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
