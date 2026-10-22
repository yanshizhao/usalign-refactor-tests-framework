#!/usr/bin/env python3
"""
TMalign regression test script
Switch to the USalign-beta branch, compile the modified TMalign, run all test
cases, and compare byte-by-byte with baseline/.
Each case runs with "-outdir ." so generated files stay in the case working
directory; those files are compared as artifacts in addition to stdout/stderr.
Generated artifacts compared: sup.pdb, matrix.txt.
Restores the branch that was active before running.
"""
import subprocess, shutil, sys, difflib, re, os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = USALIGN_DIR / "src" / "app" / "tools" / "tool_main" / "tmalign_main.cpp"
INC          = ["-I" + str(USALIGN_DIR / d) for d in (
    "src/common", "src/engine", "src/engine/tmalign", "src/engine/flexalign",
    "src/engine/mmalign", "src/engine/se", "src/engine/tmscore", "src/engine/hwrmsd",
    "src/engine/upgma", "src/output_funcs", "src/app/tools", "src/app/tools/tool_include")]
SRC          = ["src/common/common.cpp", "src/engine/engine_common.cpp", "src/engine/se/se.cpp",
    "src/engine/tmalign/TMalign.cpp", "src/output_funcs/output.cpp"]
EXE_NAME     = "TMalign_mod.exe"
ARTIFACT_GLOBS = ['sup.pdb', 'matrix.txt']
CLEAN_GLOBS    = ['*.pml']


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
    print("Compiling modified TMalign ...")
    cmd = ["g++", "-O3", "-ffast-math", "-lm", "-static"] + INC + ["-o", exe_path, str(SRC_MAIN)]
    cmd += [str(USALIGN_DIR / s) if not os.path.isabs(s) else s for s in SRC]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def strip_cpu_time(text: str) -> str:
    """Remove #Total CPU time lines (they fluctuate naturally)"""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def normalize(text: str, exe_path: str) -> str:
    return strip_cpu_time(text.replace(str(exe_path), "EXE"))


def artifact_names(workdir: Path):
    for pattern in ARTIFACT_GLOBS:
        for path in sorted(workdir.glob(pattern)):
            if path.is_file():
                yield path.name, path


def clean_artifacts(workdir: Path):
    for _, path in list(artifact_names(workdir)):
        path.unlink()
    for pattern in CLEAN_GLOBS:
        for path in workdir.glob(pattern):
            if path.is_file():
                path.unlink()


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
        clean_artifacts(workdir)

    for name, workdir_rel, args_str in cases:
        workdir = (DATA_DIR / workdir_rel).resolve()
        args = args_str.split()
        cmd = [exe_path] + args + ["-outdir", "."]

        print(f"=== {name} ===", end=" ")

        clean_artifacts(workdir)
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
        content = normalize(proc.stdout + proc.stderr, exe_path)

        (CURRENT_DIR / f"{name}.out").write_text(content, encoding="utf-8")

        base_file = BASELINE_DIR / f"{name}.out"
        if not base_file.exists():
            print("FAIL (no baseline)")
            total_fail += 1
        elif content == strip_cpu_time(base_file.read_text(encoding="utf-8")):
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

        for fname, path in artifact_names(workdir):
            dest = CURRENT_DIR / f"{name}__{fname}"
            shutil.copy2(str(path), str(dest))
            base_art = BASELINE_DIR / f"{name}__{fname}"
            if not base_art.exists():
                print(f"  {fname}: FAIL (no baseline for this artifact)")
                total_fail += 1
            elif dest.read_bytes() == base_art.read_bytes():
                print(f"  {fname}: PASS")
                total_pass += 1
            else:
                print(f"  {fname}: FAIL")
                total_fail += 1
        clean_artifacts(workdir)

    print(f"\nResults: {total_pass} PASS, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "USalign-beta":
            print(f"Switching USalign from {original_branch} to USalign-beta for TMalign regression...")
            checkout("USalign-beta")
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_mod(exe)
        ok = run_tests(exe)
    finally:
        if original_branch and original_branch != "USalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
    sys.exit(0 if ok else 1)
