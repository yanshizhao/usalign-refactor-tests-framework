#!/usr/bin/env python3
"""
xyz_sfetch regression test script
Switch to the USalign-beta branch, compile the modified xyz_sfetch, run all
test cases, and compare byte-by-byte with baseline/.
Cases that do not already pass "-outdir" get "-outdir ." appended, so index
files stay in the case working directory; the -outdir cases exercise the
index write/read path that must agree with each other.
Generated .index files are compared as artifacts in addition to stdout/stderr.
Restores the branch that was active before running.

Cases run in file order and share state: the missing-index case must come
first, and the index-building case must precede the fetching cases.
"""
import subprocess, shutil, sys, difflib
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = USALIGN_DIR / "src" / "app" / "tools" / "tool_main" / "xyz_sfetch_main.cpp"
INC          = ["-I" + str(USALIGN_DIR / d) for d in (
    "src/common", "src/app/tools", "src/app/tools/tool_include")]
COMMON_CPP   = [str(USALIGN_DIR / "src" / "common" / "common.cpp")]
EXE_NAME     = "xyz_sfetch_mod.exe"
# Logical index artifacts: name -> candidate locations, in lookup order. The
# beta branch writes "other.xyz.index" under -outdir; the default-outdir cases
# write next to the xyz file.
ARTIFACTS    = {
    "ca.xyz.index":    ["ca.xyz.index", "outdir_sub/ca.xyz.index"],
    "other.xyz.index": ["outdir_sub/other.xyz.index", "other.xyz.index"],
}


def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def compile_mod(exe_path: str):
    print("Compiling modified xyz_sfetch ...")
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static"] + INC + ["-o", exe_path, str(SRC_MAIN)] + COMMON_CPP,
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def normalize(text: str, exe_path: str) -> str:
    """Replace the executable path, which legitimately differs between runs"""
    return text.replace(str(exe_path), "EXE")


def find_artifact(workdir: Path, candidates):
    for rel in candidates:
        path = workdir / rel
        if path.exists():
            return path
    return None


def clean_state(workdir: Path):
    """Remove index files and the -outdir tree so each run starts from a known state"""
    for candidates in ARTIFACTS.values():
        for rel in candidates:
            path = workdir / rel
            if path.exists():
                path.unlink()
    sub = workdir / "outdir_sub"
    if sub.exists():
        shutil.rmtree(sub)


def run_tests(exe_path: str):
    for d in [CURRENT_DIR, DIFFS_DIR]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    if not BASELINE_DIR.exists():
        print("ERROR: baseline/ not found. Run create_baseline.py first."); sys.exit(1)

    total_pass, total_fail = 0, 0
    testcases = SCRIPT_DIR / "testcases.txt"
    with open(testcases, "r", encoding="utf-8") as f:
        cases = [line.split(maxsplit=2) for line in (l.strip() for l in f)
                 if line and not line.startswith("#")]

    for workdir in {(DATA_DIR / c[1]).resolve() for c in cases}:
        clean_state(workdir)

    for name, workdir_rel, args_str in cases:
        workdir = (DATA_DIR / workdir_rel).resolve()
        args = args_str.split()
        cmd = [exe_path] + args + ([] if "-outdir" in args else ["-outdir", "."])

        print(f"=== {name} ===", end=" ")

        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
        content = normalize(proc.stdout + proc.stderr, exe_path)

        (CURRENT_DIR / f"{name}.out").write_text(content, encoding="utf-8")

        base_file = BASELINE_DIR / f"{name}.out"
        if not base_file.exists():
            print("FAIL (no baseline)")
            total_fail += 1
        elif content == base_file.read_text(encoding="utf-8"):
            print("PASS")
            total_pass += 1
        else:
            print("FAIL")
            total_fail += 1
            with open(DIFFS_DIR / f"{name}.diff", "w", encoding="utf-8") as df:
                df.writelines(difflib.unified_diff(
                    base_file.read_text(encoding="utf-8").splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"baseline/{name}.out",
                    tofile=f"current/{name}.out"))

        # Compare the index files the case produced
        for logical, candidates in ARTIFACTS.items():
            path = find_artifact(workdir, candidates)
            base_art = BASELINE_DIR / f"{name}.{logical}"
            if path is not None:
                dest = CURRENT_DIR / f"{name}.{logical}"
                shutil.copy2(str(path), str(dest))
            if path is not None and base_art.exists():
                if (CURRENT_DIR / f"{name}.{logical}").read_bytes() == base_art.read_bytes():
                    print(f"  {logical}: PASS")
                    total_pass += 1
                else:
                    print(f"  {logical}: FAIL")
                    total_fail += 1
            elif base_art.exists():
                print(f"  {logical}: FAIL (missing output file)")
                total_fail += 1

    for workdir in {(DATA_DIR / c[1]).resolve() for c in cases}:
        clean_state(workdir)

    print(f"\nResults: {total_pass} PASS, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "USalign-beta":
            print(f"Switching USalign from {original_branch} to USalign-beta for xyz_sfetch regression...")
            checkout("USalign-beta")
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_mod(exe)
        ok = run_tests(exe)
    finally:
        if original_branch and original_branch != "USalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
    sys.exit(0 if ok else 1)
