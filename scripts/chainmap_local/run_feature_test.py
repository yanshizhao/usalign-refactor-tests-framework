#!/usr/bin/env python3
import subprocess, os, sys, re, platform
from pathlib import Path

"""
Feature test runner for -chainmap local-constraint changes.
Validates new behaviors (mapping lock, auto selection, exceptions, hints)
by asserting on stdout/stderr key lines.

Cases are read from testcases_feature.txt:
  format: name workdir(relative to data/) command... | assert1;assert2;...
  assert types:
    contains:TEXT        - output must contain TEXT
    not_contains:TEXT    - output must NOT contain TEXT
    mapping:C1->C2,...   - chain1 list must pair to chain2 list in order

Usage:
    python run_feature_test.py            # run all cases in testcases_feature.txt
    python run_feature_test.py F1 F2      # run selected cases by name
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
FEATURE_OUTPUT = SCRIPT_DIR / "feature_output"
CASES_FILE = SCRIPT_DIR / "testcases_feature.txt"
EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = SCRIPT_DIR / f"USalign_chainmap_new{EXE_SUFFIX}"


def read_cases(cases_file):
    """Read feature cases from txt:
    'name workdir command... | assert1;assert2;...' (lines starting with # skipped)."""
    cases = {}
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " | " in line:
                cmd_part, assert_part = line.split(" | ", 1)
            else:
                cmd_part, assert_part = line, ""
            parts = cmd_part.split(maxsplit=2)
            if len(parts) < 3:
                continue
            name, workdir, cmd = parts
            asserts = []
            for a in assert_part.split(";"):
                a = a.strip()
                if not a:
                    continue
                if ":" in a:
                    kind, _, param = a.partition(":")
                    asserts.append((kind.strip(), param))
            cases[name] = {"workdir": workdir, "cmd": cmd.split(), "asserts": asserts}
    return cases


def run_case(cmd, workdir, name):
    """Run one feature case and save its full output (stdout+stderr) to
    feature_output/<name>.out for manual review, consistent with the
    regression runner's output-retention policy."""
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
    if not FEATURE_OUTPUT.exists():
        FEATURE_OUTPUT.mkdir(parents=True)
    (FEATURE_OUTPUT / f"{name}.out").write_text(
        proc.stdout + proc.stderr, encoding="utf-8")
    return proc


def chain_list_from_outfmt2(text):
    """Extract chain lists from -outfmt 2 output line:
    name:1,A:1,B:1,C<TAB>name:1,A:1,B:1,C<TAB>TM...
    Returns (chain1_list, chain2_list) or None."""
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        def chains(s):
            return re.findall(r':\d+,([A-Za-z0-9_]+)', s) or re.findall(r':([A-Za-z0-9_]+)', s)
        c1 = chains(parts[0])
        c2 = chains(parts[1])
        if c1 and c2:
            return c1, c2
    return None


def check_asserts(name, proc, asserts):
    text = proc.stdout + proc.stderr
    failures = []
    for kind, expected in asserts:
        if kind == "contains":
            if expected not in text:
                failures.append("missing text: " + repr(expected))
        elif kind == "not_contains":
            if expected in text:
                failures.append("unexpected text: " + repr(expected))
        elif kind == "mapping":
            got = chain_list_from_outfmt2(text)
            if got is None:
                failures.append("cannot parse chain mapping from -outfmt 2 output")
            else:
                c1, c2 = got
                expected_pairs = [p.strip().split("->") for p in expected.split(",")]
                for i, (a, b) in enumerate(expected_pairs):
                    if i >= len(c1) or i >= len(c2) or c1[i] != a or c2[i] != b:
                        failures.append("mapping[%d] expected %s->%s, got %s->%s" % (
                            i, a, b, c1[i] if i < len(c1) else "?", c2[i] if i < len(c2) else "?"))
        else:
            failures.append("unknown assert kind: " + kind)
    return failures


def main():
    if not EXE.exists():
        print("ERROR: test executable not found:", EXE)
        print("Run run_regression.py first (it compiles the executable).")
        sys.exit(1)
    if not CASES_FILE.exists():
        print("ERROR: cases file not found:", CASES_FILE)
        sys.exit(1)

    cases = read_cases(CASES_FILE)
    selected = sys.argv[1:] if len(sys.argv) > 1 else list(cases)

    total = passed = failed = 0
    for name in selected:
        if name not in cases:
            print("SKIP unknown case:", name)
            continue
        case = cases[name]
        workdir = (DATA_DIR / case["workdir"]).resolve()
        cmd = [str(EXE)] + case["cmd"]
        print("=== " + name + " ===")
        print("  CMD:", " ".join(case["cmd"]))
        proc = run_case(cmd, workdir, name)
        failures = check_asserts(name, proc, case["asserts"])
        total += 1
        if failures:
            failed += 1
            for f in failures:
                print("  FAIL:", f)
        else:
            passed += 1
            print("  PASS")
    print("\n===== Feature summary: %d passed, %d failed (total %d) =====" % (passed, failed, total))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
