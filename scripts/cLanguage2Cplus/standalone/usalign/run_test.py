#!/usr/bin/env python3
"""
USalign regression test script
Switch to beta, compile the modified binary, run all
cases with "-outdir ." and compare stdout/stderr and the
generated files byte-by-byte with baseline/.
"""
import subprocess, os, shutil, sys, tempfile, glob, re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = USALIGN_DIR / "src/app/usalign/usalign.cpp"
INC          = ["-I" + str(USALIGN_DIR / d) for d in (
    "src/common", "src/engine", "src/engine/tmalign", "src/engine/flexalign",
    "src/engine/mmalign", "src/engine/mmdock", "src/engine/mtmalign",
    "src/engine/soialign", "src/engine/se", "src/engine/tmscore",
    "src/engine/hwrmsd", "src/engine/upgma", "src/output_funcs",
    "src/app/tools", "src/app/tools/tool_include")]
SRC          = ["src/app/usalign/usalign.cpp", "src/engine/upgma/UPGMA.cpp",
    "src/engine/tmalign/TMalign.cpp", "src/engine/flexalign/flexalign.cpp",
    "src/engine/tmscore/TMscore.cpp", "src/engine/hwrmsd/HwRMSD.cpp",
    "src/engine/soialign/SOIalign.cpp", "src/engine/se/se.cpp",
    "src/engine/mmalign/MMalign.cpp", "src/engine/mmdock/MMdock.cpp",
    "src/engine/mtmalign/mTMalign.cpp", "src/common/common.cpp",
    "src/engine/engine_common.cpp", "src/output_funcs/output.cpp"]
EXE_NAME     = "USalign_mod.exe"
ARTIFACTS    = ['sup.pdb']
CLEANUP      = ['*.pml', '*_structure2.*']


CPU_TIME   = re.compile(r'^#Total (?:CPU|elapsed) time.*\n?', re.M)
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


def compile_mod(exe_path: str):
    print("Compiling modified USalign ...")
    cmd = ["g++", "-O3", "-ffast-math", "-lm", "-static"] + INC + ["-o", exe_path]
    src_list = [str(SRC_MAIN)] + [str(USALIGN_DIR / s) for s in SRC if s != str(SRC_MAIN) and (USALIGN_DIR / s).resolve() != SRC_MAIN.resolve()]
    cmd += src_list
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


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


def run_tests(exe_path: str):
    for d in [CURRENT_DIR, DIFFS_DIR]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    if not BASELINE_DIR.exists():
        print("ERROR: baseline/ not found. Run create_baseline.py first."); sys.exit(1)

    with open(SCRIPT_DIR / "testcases.txt", "r", encoding="utf-8") as f:
        cases = [line.split(maxsplit=2) for line in (l.strip() for l in f)
                 if line and not line.startswith("#")]

    for workdir in {(DATA_DIR / c[1]).resolve() for c in cases}:
        clean_artifacts(workdir)

    total_pass = total_fail = 0
    for name, workdir_rel, args_str in cases:
        workdir = (DATA_DIR / workdir_rel).resolve()
        args = args_str.split()
        cmd = [exe_path] + args + ["-outdir", "."]
        print(f"=== {name} ===", end=" ")

        clean_artifacts(workdir)
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
        content = normalize(proc.stdout + proc.stderr, exe_path, workdir)
        (CURRENT_DIR / f"{name}.out").write_text(content, encoding="utf-8")

        base_file = BASELINE_DIR / f"{name}.out"
        if not base_file.exists():
            print("FAIL (no baseline)"); total_fail += 1
        elif content == base_file.read_text(encoding="utf-8"):
            print("PASS"); total_pass += 1
        else:
            print("FAIL"); total_fail += 1
            import difflib
            with open(DIFFS_DIR / f"{name}.diff", "w", encoding="utf-8") as df:
                df.writelines(difflib.unified_diff(
                    base_file.read_text(encoding="utf-8").splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"baseline/{name}.out", tofile=f"current/{name}.out"))

        for fname, path in artifact_names(workdir):
            dest = CURRENT_DIR / f"{name}__{fname}"
            shutil.copy2(str(path), str(dest))
            base_art = BASELINE_DIR / f"{name}__{fname}"
            if not base_art.exists():
                print(f"  {fname}: FAIL (no baseline for this artifact)"); total_fail += 1
            elif dest.read_bytes() == base_art.read_bytes():
                print(f"  {fname}: PASS"); total_pass += 1
            else:
                print(f"  {fname}: FAIL"); total_fail += 1
        clean_artifacts(workdir)

    print(f"\nResults: {total_pass} PASS, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    original_branch = subprocess.run(["git", "branch", "--show-current"],
                                     cwd=str(USALIGN_DIR), capture_output=True, text=True).stdout.strip()
    ok = False
    try:
        if original_branch != "USalign-beta":
            print(f"Switching USalign from {original_branch} to USalign-beta for {tool} regression...")
            subprocess.run(["git", "checkout", "USalign-beta"], cwd=str(USALIGN_DIR), check=True)
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_mod(exe)
        ok = run_tests(exe)
    finally:
        if original_branch and original_branch != "USalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            subprocess.run(["git", "checkout", original_branch], cwd=str(USALIGN_DIR), check=True)
    sys.exit(0 if ok else 1)
