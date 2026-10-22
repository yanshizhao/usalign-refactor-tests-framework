#!/usr/bin/env python3
"""
xyz_sfetch baseline creation script
Switch to the clean master branch, extract unmodified source code, compile the
original xyz_sfetch, run all test cases, and save output to baseline/.
master has no -outdir option, so "-outdir <dir>" is stripped from the arguments
here: master writes the index into the working directory instead, and the index
content is identical either way.
The index file written by each case is saved as an artifact.
Restores the branch that was active before running.

Cases run in file order and share state: the missing-index case must come
first, and the index-building case must precede the fetching cases.
"""
import subprocess, os, shutil, sys, tempfile, platform
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
SRC_MAIN     = "xyz_sfetch.cpp"
EXE_NAME     = "xyz_sfetch_orig.exe"
# Logical index artifacts: name -> candidate locations, in lookup order. The
# beta branch writes "other.xyz.index" under -outdir; master writes it next to
# the xyz file, so both locations are probed and the first hit is compared.
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
    print("Compiling original xyz_sfetch from master ...")
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


def master_args(args):
    """Strip '-outdir <dir>' from a beta-branch argument list."""
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "-outdir":
            skip = True
            continue
        out.append(a)
    return out


def requested_outdir(args):
    for i, a in enumerate(args):
        if a == "-outdir" and i + 1 < len(args):
            return args[i + 1]
    return None


def find_artifact(workdir: Path, candidates):
    for rel in candidates:
        path = workdir / rel
        if path.exists():
            return path
    return None


def snapshot(workdir: Path):
    """Map logical artifact name -> (path, bytes) for every artifact present"""
    state = {}
    for logical, candidates in ARTIFACTS.items():
        path = find_artifact(workdir, candidates)
        if path is not None:
            state[logical] = (path, path.read_bytes())
    return state


def produced_by(before, after):
    """Artifacts that this case created or rewrote; unchanged leftovers from a
    previous case in the shared working directory are not attributed to it."""
    return {logical: data
            for logical, (_, data) in after.items()
            if logical not in before or before[logical][1] != data}


def mirror_into_outdir(workdir: Path, outdir: str):
    """master has no -outdir, so an index it writes beside the xyz file is
    copied into the -outdir location that the beta branch uses, letting both
    runs be compared on the same logical artifact. The working-directory copy
    is kept so a later fetch case, which master runs without -outdir, still
    finds the index."""
    for logical, candidates in ARTIFACTS.items():
        src = find_artifact(workdir, [c for c in candidates if "/" not in c])
        dest = workdir / outdir / logical
        if src is not None and src != dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))


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


def run_baseline(exe_path: str):
    if BASELINE_DIR.exists():
        shutil.rmtree(BASELINE_DIR)
    BASELINE_DIR.mkdir(parents=True)

    testcases = SCRIPT_DIR / "testcases_baseline.txt"
    with open(testcases, "r", encoding="utf-8") as f:
        cases = [line.split(maxsplit=2) for line in (l.strip() for l in f)
                 if line and not line.startswith("#")]

    workdirs = {(DATA_DIR / c[1]).resolve() for c in cases}
    for workdir in workdirs:
        clean_state(workdir)

    for name, workdir_rel, args_str in cases:
        workdir = (DATA_DIR / workdir_rel).resolve()
        args = master_args(args_str.split())
        cmd = [exe_path] + args

        print(f"=== {name} ===")
        print(f"  CWD: {workdir}")
        print(f"  CMD: {' '.join(cmd)}")

        before = snapshot(workdir)
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
        content = normalize(proc.stdout + proc.stderr, exe_path)
        (BASELINE_DIR / f"{name}.out").write_text(content, encoding="utf-8")

        outdir = requested_outdir(args_str.split())
        if outdir:
            mirror_into_outdir(workdir, outdir)

        # Save only artifacts this case actually produced, so a later case
        # does not inherit an earlier case's index through the shared workdir.
        for logical, data in produced_by(before, snapshot(workdir)).items():
            (BASELINE_DIR / f"{name}.{logical}").write_bytes(data)

    for workdir in workdirs:
        clean_state(workdir)

    print("\nxyz_sfetch baseline created.")


if __name__ == "__main__":
    original_branch = current_branch()
    tmpdir = tempfile.mkdtemp(prefix="xyz_sfetch_orig_")
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for xyz_sfetch baseline...")
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
