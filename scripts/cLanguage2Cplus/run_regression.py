#!/usr/bin/env python3
import subprocess, os, sys, shutil, difflib, re, platform
from pathlib import Path


"""
Regression test execution script (Regression Runner)
Features:
  1. Switch to the USalign-beta branch, compile US-align with the required modifications (USalign_mod.exe)
  2. Automatically clean the current/ and diffs/ directories before each run to avoid interference from old data
  3. Read all functional test cases from testcases_functional.txt
  4. Run each test case sequentially, saving output to the current/ directory (with _mod suffix appended to filenames)
  5. Compare the modified output against the original baseline in baseline/ (strip CPU time first)
  6. If identical, report PASS
  7. If only CPU time differs, report WARNING and generate a diff file in diffs/
  8. If business data differs, report FAIL and generate a diff file in diffs/
  9. Support special handling for superposed_structure: automatically move and clean up .pml files
Note: Run this script after modifying US-align source code to verify the changes did not introduce functional regressions.
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
CURRENT = SCRIPT_DIR / "current"
DIFFS   = SCRIPT_DIR / "diffs"
BASELINE= SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = [USALIGN_DIR / "USalign.cpp", USALIGN_DIR / "UPGMA.cpp"]

# Cross-platform executable path: add .exe only on Windows
EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = SCRIPT_DIR / f"USalign_mod_{os.getpid()}{EXE_SUFFIX}"
MOD_SUFFIX = "_mod"


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
    print("Compiling modified US-align from USalign-beta...")
    compile_cmd = ["g++", "-O3", "-ffast-math", "-fopenmp", "-o", str(EXE)] + [str(s) for s in SRC]
    if platform.system() == "Windows":
        compile_cmd.insert(4, "-static-libgcc")
        compile_cmd.insert(5, "-static-libstdc++")
    if subprocess.run(compile_cmd).returncode != 0:
        print("Compilation failed!"); sys.exit(1)


def clean_directory(dir_path):
    if dir_path.exists():
        shutil.rmtree(dir_path, ignore_errors=True)
    dir_path.mkdir(parents=True, exist_ok=True)


def clean_slash(text: str) -> str:
    """Remove redundant '/' prefix in output paths (both 'Name of Structure_X:' and table columns)"""
    text = re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)
    text = re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', text, flags=re.MULTILINE)
    return text


def strip_cpu_time(text: str) -> str:
    """Remove #Total CPU time lines -- CPU time naturally fluctuates and is not used for regression decisions"""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def is_non_business_line(line: str) -> bool:
    """Determine whether a diff line is non-business content (CPU time, etc., environmental differences)"""
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

    with open("testcases_functional.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split()
            cmd = [str(EXE)] + args_list
            print(f"Running {name} ...")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            # Capture output, clean it, then write to file
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr
            content = clean_slash(content)

            out_filename = f"{name}{MOD_SUFFIX}.out"
            out_file = CURRENT / out_filename
            with open(out_file, "w", encoding="utf-8") as of:
                of.write(content)

            # ---- Parallel determinism + serial sanity checks (parallel cases only) ----
            # For every -threads case, additionally:
            #   1. run the parallel command a second time and assert the two
            #      parallel runs produce identical output (data-race nondeterminism
            #      would make the output scheduling-dependent; repeat runs raise
            #      the detection probability vs a single run vs baseline)
            #   2. run once with -threads 1 and assert:
            #      a. serial run does not crash
            #      b. serial output == parallel output (excluding CPU time)
            serial_ok = True
            if name != "superposed_structure" and "-threads" in args_list:
                # --- parallel repeat run (determinism) ---
                proc_parallel2 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
                if proc_parallel2.returncode != 0:
                    print(f"  FAIL: parallel repeat run crashed (exit {proc_parallel2.returncode})")
                    serial_ok = False
                else:
                    parallel2_content = strip_cpu_time(clean_slash(proc_parallel2.stdout + proc_parallel2.stderr))
                    parallel_content = strip_cpu_time(content)
                    if parallel2_content != parallel_content:
                        print("  FAIL: parallel repeat runs differ (data race nondeterminism)")
                        serial_ok = False
                with open(CURRENT / f"{name}_repeat.out", "w", encoding="utf-8") as of:
                    of.write(clean_slash(proc_parallel2.stdout + proc_parallel2.stderr))
                # --- serial run (sanity + consistency) ---
                serial_args = []
                skip_next = False
                for a in args_list:
                    if skip_next:
                        skip_next = False
                        continue
                    if a == "-threads":
                        serial_args += ["-threads", "1"]
                        skip_next = True
                    else:
                        serial_args.append(a)
                cmd_serial = [str(EXE)] + serial_args
                proc_serial = subprocess.run(cmd_serial, capture_output=True, text=True, cwd=str(workdir))
                if proc_serial.returncode != 0:
                    print(f"  FAIL: serial run crashed (exit {proc_serial.returncode})")
                    serial_ok = False
                else:
                    serial_content = strip_cpu_time(clean_slash(proc_serial.stdout + proc_serial.stderr))
                    if serial_content != parallel_content:
                        print("  FAIL: serial vs parallel output differs (possible data race)")
                        serial_ok = False
                # Save serial output (cleaned, consistent with the parallel
                # current/<name>_mod.out) for manual inspection
                with open(CURRENT / f"{name}_serial.out", "w", encoding="utf-8") as of:
                    of.write(clean_slash(proc_serial.stdout + proc_serial.stderr))

            if name == "superposed_structure":
                total += 1
                sup_pdb = workdir / "sup.pdb"
                if sup_pdb.exists():
                    shutil.move(str(sup_pdb), str(CURRENT / f"sup{MOD_SUFFIX}.pdb"))
                for pml in workdir.glob("*.pml"):
                    pml.unlink()
                result = _diff_binary("sup.pdb", f"sup{MOD_SUFFIX}.pdb", name, " (structure)")
                if result == "PASS":
                    passed += 1
                else:
                    failed += 1
            else:
                total += 1
                result = _diff_files(f"{name}.out", out_filename, name)
                if result == "PASS" and serial_ok:
                    passed += 1
                elif result == "WARNING" and serial_ok:
                    warned += 1
                else:
                    failed += 1

    print(f"\n=== Summary: total={total}, PASS={passed}, WARNING={warned}, FAIL={failed} ===")
    return failed == 0


def _diff_files(base_filename, mod_filename, tag, extra_note=""):
    """Compare text output files with CPU-time-aware classification.

    Returns: "PASS" (identical), "WARNING" (only CPU time differs), "FAIL" (business data differs)
    """
    base = BASELINE / base_filename
    curr = CURRENT / mod_filename
    diff = DIFFS / f"{tag}.diff"
    try:
        btext = clean_slash(strip_cpu_time(base.read_text(encoding="utf-8", errors="replace")))
        ctext = clean_slash(strip_cpu_time(curr.read_text(encoding="utf-8", errors="replace")))
        if btext == ctext:
            print(f"  PASS{extra_note}")
            if diff.exists():
                diff.unlink()
            return "PASS"

        # generate diff and classify lines
        blines = btext.splitlines(keepends=True)
        clines = ctext.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            blines, clines, fromfile=str(base), tofile=str(curr)
        ))
        with open(diff, "w", encoding="utf-8") as df:
            df.writelines(diff_lines)

        has_business = False
        for line in diff_lines:
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@') or line.startswith(' '):
                continue
            content = line[1:].strip()
            if line.startswith('-') or line.startswith('+'):
                if not is_non_business_line(content):
                    has_business = True
                    break

        if has_business:
            print(f"  FAIL{extra_note} (business data mismatch, see {diff})")
            return "FAIL"
        else:
            print(f"  WARNING{extra_note} (CPU time only, see {diff})")
            return "WARNING"
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return "ERROR"


def _diff_binary(base_filename, mod_filename, tag, extra_note=""):
    """Byte-level comparison for structure files (.pdb, .sup).

    Returns: "PASS" (identical) or "FAIL" (any byte difference)
    """
    base = BASELINE / base_filename
    curr = CURRENT / mod_filename
    diff = DIFFS / f"{tag}.diff"
    try:
        if base.read_bytes() == curr.read_bytes():
            print(f"  PASS{extra_note}")
            if diff.exists():
                diff.unlink()
            return "PASS"
        else:
            print(f"  FAIL{extra_note} (structure file mismatch, see {diff})")
            blines = base.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            clines = curr.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            with open(diff, "w", encoding="utf-8") as df:
                df.writelines(difflib.unified_diff(
                    blines, clines, fromfile=str(base), tofile=str(curr)
                ))
            return "FAIL"
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return "ERROR"


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "USalign-beta":
            print(f"Switching USalign from {original_branch} to USalign-beta for functional regression...")
            checkout("USalign-beta")
        compile()
        run_tests()
    finally:
        if EXE.exists():
            EXE.unlink()
        if original_branch and original_branch != "USalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)