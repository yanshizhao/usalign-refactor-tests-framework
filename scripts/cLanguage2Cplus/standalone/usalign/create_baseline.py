#!/usr/bin/env python3
"""
USalign baseline creation script
Switch to master, compile the original binary, run
all cases and save stdout/stderr (plus generated files)
to baseline/. Restores the previous branch.
"""
import subprocess, os, shutil, sys, tempfile, glob, re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = "USalign.cpp"
EXE_NAME     = "USalign_orig.exe"
ARTIFACTS    = ['sup.pdb']
CLEANUP      = ['*.pml', '*_structure2.*']


CPU_TIME   = re.compile(r'^#Total CPU time.*\n?', re.M)
# Rotation matrices printed with %10.10f: the refactor reassociates the floating
# point reductions, so digits past 6 decimals move by one unit in the last place.
LONG_DECIMAL = re.compile(r'(?<![\d.])-?\d+\.\d{6,}')
# Beta-only chain-pairing summary appended by the -mm 1 / -TMscore 6 paths.
CHAIN_SUMMARY = re.compile(r'^# (?:Chain pairing summary:|  Protein:|  RNA:|'
                           r'  Chainmap:|Unpaired:|  )')


def normalize(text: str, exe_path: str, workdir: Path) -> str:
    """Drop run-dependent and beta-only additions, round 10-dp floats to 6 dp."""
    text = text.replace(str(exe_path), "EXE").replace(str(workdir) + "/", "")
    text = CPU_TIME.sub("", text)
    text = LONG_DECIMAL.sub(lambda m: f"{float(m.group(0)):.6f}", text)
    # -0.000000 and 0.000000 print the same value; sign of zero is not meaningful.
    # Dropping the sign shortens the field, so rebuild the column alignment of
    # purely numeric rows (matrix rows) with single-space separation.
    text = text.replace("-0.000000", "0.000000")
    lines = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        if body.strip() and re.match(r'^[\s\-+0-9.eE]+$', body):
            body = re.sub(r'[ 	]+', ' ', body.strip())
        lines.append(body + ("\n" if line.endswith("\n") else ""))
    text = "".join(lines)
    text = "\n".join(l for l in text.splitlines() if not CHAIN_SUMMARY.match(l))
    return text



def compile_orig(exe_path: str, tmpdir: str):
    print("Compiling original USalign from master ...")
    src = os.path.join(tmpdir, "USalign.cpp")
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static", "-I", tmpdir, "-o", exe_path, src],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def extract_master_sources(tmpdir: str):
    """Extract all .cpp and .h files of the master branch into tmpdir"""
    result = subprocess.run(["git", "ls-tree", "--name-only", "-r", "master"],
                            capture_output=True, text=True, cwd=str(USALIGN_DIR))
    if result.returncode != 0:
        print("ERROR: cannot list master branch"); sys.exit(1)
    for fname in result.stdout.strip().split("\n"):
        if not fname.endswith((".cpp", ".h")):
            continue
        content = subprocess.run(["git", "show", f"master:{fname}"],
                                 capture_output=True, text=True, cwd=str(USALIGN_DIR))
        if content.returncode != 0:
            print(f"WARNING: skip {fname}"); continue
        dst = os.path.join(tmpdir, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content.stdout)


def artifact_names(workdir: Path):
    for pattern in ARTIFACTS:
        for path in sorted(workdir.glob(pattern)):
            if path.is_file():
                yield path.name, path


def clean_artifacts(workdir: Path):
    """Remove compared artifacts and viewer scripts so each run starts clean"""
    for _, path in list(artifact_names(workdir)):
        path.unlink()
    for pattern in CLEANUP:
        for path in workdir.glob(pattern):
            if path.is_file():
                path.unlink()


def run_baseline(exe_path: str):
    if BASELINE_DIR.exists():
        shutil.rmtree(BASELINE_DIR)
    BASELINE_DIR.mkdir(parents=True)

    with open(SCRIPT_DIR / "testcases_baseline.txt", "r", encoding="utf-8") as f:
        cases = [line.split(maxsplit=2) for line in (l.strip() for l in f)
                 if line and not line.startswith("#")]

    for workdir in {(DATA_DIR / c[1]).resolve() for c in cases}:
        clean_artifacts(workdir)

    for name, workdir_rel, args_str in cases:
        workdir = (DATA_DIR / workdir_rel).resolve()
        args = args_str.split()
        cmd = [exe_path] + args
        print(f"=== {name} ===")
        print(f"  CWD: {workdir}")
        print(f"  CMD: {' '.join(cmd)}")

        clean_artifacts(workdir)
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
        content = normalize(proc.stdout + proc.stderr, exe_path, workdir)
        (BASELINE_DIR / f"{name}.out").write_text(content, encoding="utf-8")

        for fname, path in artifact_names(workdir):
            shutil.copy2(str(path), str(BASELINE_DIR / f"{name}__{fname}"))
        clean_artifacts(workdir)

    print("\nUSalign baseline created.")


if __name__ == "__main__":
    original_branch = subprocess.run(["git", "branch", "--show-current"],
                                     cwd=str(USALIGN_DIR), capture_output=True, text=True).stdout.strip()
    tmpdir = tempfile.mkdtemp(prefix="USalign_orig_")
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for USalign baseline...")
            subprocess.run(["git", "checkout", "master"], cwd=str(USALIGN_DIR), check=True)
        extract_master_sources(tmpdir)
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_orig(exe, tmpdir)
        run_baseline(exe)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            subprocess.run(["git", "checkout", original_branch], cwd=str(USALIGN_DIR), check=True)
