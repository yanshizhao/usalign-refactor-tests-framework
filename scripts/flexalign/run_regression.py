#!/usr/bin/env python3
"""
Regression test runner for -mm 7 (flexible alignment).
Compares outputs between master (baseline) and USalign-beta (current) branches.
"""
import subprocess
import os
import sys
import shutil
import re
import difflib
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
CURRENT = SCRIPT_DIR / "current"
BASELINE = SCRIPT_DIR / "baseline"
DIFFS = SCRIPT_DIR / "diffs"

USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
INC = ["-I" + str(USALIGN_DIR / d) for d in (
    "src/common", "src/engine", "src/engine/tmalign", "src/engine/flexalign", "src/engine/mmalign", "src/engine/mmdock", "src/engine/mtmalign",
    "src/engine/soialign", "src/engine/se", "src/engine/tmscore", "src/engine/hwrmsd",
    "src/engine/upgma", "src/output_funcs", "src/app/tools")]
COMMON = [USALIGN_DIR / "src" / "common" / "common.cpp"]
ENGINE = [USALIGN_DIR / "src" / "engine" / "engine_common.cpp", USALIGN_DIR / "src" / "engine" / "se" / "se.cpp", USALIGN_DIR / "src" / "engine" / "tmalign" / "TMalign.cpp", USALIGN_DIR / "src" / "engine" / "mmalign" / "MMalign.cpp", USALIGN_DIR / "src" / "engine" / "mmdock" / "MMdock.cpp", USALIGN_DIR / "src" / "engine" / "mtmalign" / "mTMalign.cpp", USALIGN_DIR / "src" / "engine" / "flexalign" / "flexalign.cpp", USALIGN_DIR / "src" / "engine" / "soialign" / "SOIalign.cpp"]
ORCH = [USALIGN_DIR / "src" / "output_funcs" / "output.cpp"]
SRC = [USALIGN_DIR / "src" / "app" / "usalign" / "usalign.cpp", USALIGN_DIR / "src" / "engine" / "upgma" / "UPGMA.cpp"] + COMMON + ENGINE + ORCH

EXE_SUFFIX = ".exe" if os.name == "nt" else ""
EXE_BETA   = SCRIPT_DIR / f"USalign_mod{EXE_SUFFIX}"

BETA_BRANCH   = "USalign-beta"


def current_branch():
    try:
        r = subprocess.run(["git", "branch", "--show-current"],
                           cwd=str(USALIGN_DIR), capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def checkout(branch):
    r = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Failed to checkout {branch}: {r.stderr}")
        sys.exit(1)


def compile_exe(branch, exe_path):
    """Compile USalign from the specified branch to exe_path."""
    print(f"Compiling USalign from {branch} branch...")
    checkout(branch)
    # Use the same compilation command as readme.txt for consistency
    cmd = ["g++", "-O3", "-ffast-math", "-std=gnu++11", "-fopenmp"] + INC + [
           "-o", str(exe_path)] + [str(s) for s in SRC]
    if os.name == "nt":
        # Windows: use static linking
        cmd.insert(4, "-static")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("Compilation failed!"); sys.exit(1)
    print(f"  -> {exe_path}")


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (same as cLanguage2Cplus)."""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def strip_cpu_time(text: str) -> str:
    """Remove CPU time lines (non-deterministic)."""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def clean_output(text: str) -> str:
    """Apply all cleaning steps for comparison."""
    text = clean_slash(text)
    text = strip_cpu_time(text)
    return text


STRUCTURE2_PRODUCT = re.compile(r"_structure2\.[^.]+$")
PYMOL_STRUCTURE2_LOAD = re.compile(rb'^cmd\.load\(.*, "structure2"\)', re.MULTILINE)
PYMOL_STRUCTURE2_TOKEN = b'cmd.load("<structure2>", "structure2")'


def run_case(exe, workdir, args_list):
    """Run one test case and return cleaned stdout+stderr."""
    # Inject -threads 1 for deterministic floating-point output
    cmd = [str(exe)] + args_list + ["-threads", "1"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
    return clean_output(proc.stdout + proc.stderr)


def main():
    original = current_branch()
    try:
        # Step 1: Compile beta (current)
        compile_exe(BETA_BRANCH, EXE_BETA)

        # Step 3: Clean output dirs
        for d in [CURRENT, DIFFS]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)

        # Step 4: Read test cases
        cases_file = SCRIPT_DIR / "testcases_functional.txt"
        if not cases_file.exists():
            print(f"Test cases file not found: {cases_file}"); sys.exit(1)

        with open(cases_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total = passed = warned = failed = 0

        # Baseline directory holds the golden outputs generated from master
        if not BASELINE.exists():
            print(f"Baseline directory not found: {BASELINE}"); sys.exit(1)

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            name, workdir_rel, args_str = parts
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split() + ["-outdir", "."]

            print(f"\n=== {name} ===")

            # Run with beta (current); snapshot new product files (-o/-rasmol/-chimerax)
            before = {p.name for p in workdir.iterdir() if p.is_file()}
            cur_text = run_case(EXE_BETA, workdir, args_list)
            prod_dir = CURRENT / f"{name}.prod"
            if prod_dir.exists():
                shutil.rmtree(prod_dir, ignore_errors=True)
            prod_dir.mkdir(parents=True, exist_ok=True)
            for p in workdir.iterdir():
                if p.is_file() and p.name not in before:
                    shutil.copy2(p, prod_dir / p.name)
                    p.unlink()
            cur_file = CURRENT / f"{name}.out"
            with open(cur_file, "w", encoding="utf-8") as of:
                of.write(cur_text)

            # Read the golden baseline
            base_file = BASELINE / f"{name}.out"
            if not base_file.exists():
                print(f"  FAIL - baseline missing: {base_file}")
                failed += 1
                total += 1
                continue
            with open(base_file, "r", encoding="utf-8") as bf:
                base_text = clean_output(bf.read())

            # Compare product files byte-by-byte (if any)
            prod_ok = True
            base_prod = BASELINE / f"{name}.prod"
            base_files = {p.name for p in base_prod.iterdir()
                          if not STRUCTURE2_PRODUCT.search(p.name)} if base_prod.exists() else set()
            cur_files = {p.name for p in prod_dir.iterdir()
                         if not STRUCTURE2_PRODUCT.search(p.name)}
            if base_files != cur_files:
                print(f"  FAIL - product file set differs: base={sorted(base_files)} cur={sorted(cur_files)}")
                prod_ok = False
            else:
                for fn in sorted(base_files):
                    base_data = PYMOL_STRUCTURE2_LOAD.sub(PYMOL_STRUCTURE2_TOKEN, (base_prod / fn).read_bytes())
                    cur_data = PYMOL_STRUCTURE2_LOAD.sub(PYMOL_STRUCTURE2_TOKEN, (prod_dir / fn).read_bytes())
                    if base_data != cur_data:
                        print(f"  FAIL - product file differs: {fn}")
                        prod_ok = False

            # Compare
            if base_text == cur_text and prod_ok:
                print(f"  PASS")
                passed += 1
            else:
                # Generate unified diff
                base_lines = base_text.splitlines()
                cur_lines = cur_text.splitlines()
                diff = list(difflib.unified_diff(
                    base_lines, cur_lines,
                    fromfile=f"baseline/{name}.out",
                    tofile=f"current/{name}.out",
                    lineterm=""
                ))
                # Filter out non-business lines (CPU time, blank)
                business_diff = [l for l in diff
                                 if (l.startswith("+") or l.startswith("-"))
                                 and not l.startswith(("+++", "---"))
                                 and not l.strip().startswith("#Total CPU time")
                                 and l.strip() not in ("+", "-")]

                if not business_diff:
                    print(f"  WARNING (only CPU time / formatting differences)")
                    warned += 1
                else:
                    print(f"  FAIL - business output differs")
                    failed += 1

                # Write diff file
                diffs_file = DIFFS / f"{name}.diff"
                with open(diffs_file, "w", encoding="utf-8") as df:
                    df.write("\n".join(diff) + "\n")
                if business_diff:
                    print(f"  Diff -> {diffs_file}")
                    # Print first few diff lines for quick inspection
                    for dl in business_diff[:10]:
                        print(f"    {dl}")

            total += 1

        print(f"\n===== Summary: total={total}, PASS={passed}, WARNING={warned}, FAIL={failed} =====")
        return 0 if failed == 0 else 1

    finally:
        if original and original != BETA_BRANCH:
            print(f"Restoring branch to {original}...")
            checkout(original)


if __name__ == "__main__":
    sys.exit(main())
