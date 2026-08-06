#!/usr/bin/env python3
import subprocess, os, sys, re, platform
from pathlib import Path

"""
Feature test runner for -chainmap local-constraint changes.
Validates new behaviors (mapping lock, auto selection, exceptions, hints)
by asserting on stdout/stderr key lines.

Usage:
    python run_feature_test.py            # run all feature cases
    python run_feature_test.py F1 F2      # run selected cases by name
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
FEATURE_OUTPUT = SCRIPT_DIR / "feature_output"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
EXE_SUFFIX = ".exe" if platform.system() == "Windows" else ""
EXE = SCRIPT_DIR / f"USalign_chainmap_new{EXE_SUFFIX}"

# RNA single chain (chain A) from mm1/MSTATest for type-mismatch cases
RNA_PDB = (SCRIPT_DIR / ".." / "mm1" / "data" / "MSTATest" / "US7351924051.pdb").resolve()
# 4iaj / 4jhm multimer data for quality-protection / lock-conflict cases
PDB_4IAJ = (SCRIPT_DIR / ".." / "cLanguage2Cplus" / "data" / "4iaj.pdb1").resolve()
PDB_4JHM = (SCRIPT_DIR / ".." / "cLanguage2Cplus" / "data" / "4jhm.pdb1").resolve()


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


def run_case(case, name):
    """Run one feature case and save its full output (stdout+stderr) to
    feature_output/<name>.out for manual review, consistent with the
    regression runner's output-retention policy."""
    cmd = [str(EXE)] + case["cmd"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DATA_DIR))
    if not FEATURE_OUTPUT.exists():
        FEATURE_OUTPUT.mkdir(parents=True)
    (FEATURE_OUTPUT / f"{name}.out").write_text(
        proc.stdout + proc.stderr, encoding="utf-8")
    return proc


def check_asserts(name, proc, asserts):
    text = proc.stdout + proc.stderr
    failures = []
    for kind, expected in asserts:
        if kind == "contains":
            if expected not in text:
                failures.append(f"missing text: {expected!r}")
        elif kind == "not_contains":
            if expected in text:
                failures.append(f"unexpected text: {expected!r}")
        elif kind == "mapping":
            got = chain_list_from_outfmt2(text)
            if got is None:
                failures.append("cannot parse chain mapping from -outfmt 2 output")
            else:
                c1, c2 = got
                for i, (a, b) in enumerate(expected):
                    if i >= len(c1) or i >= len(c2) or c1[i] != a or c2[i] != b:
                        failures.append(f"mapping[{i}] expected {a}->{b}, got {c1[i] if i<len(c1) else '?'}->{c2[i] if i<len(c2) else '?'}")
        else:
            failures.append(f"unknown assert kind: {kind}")
    return failures


# ============================================================
# Feature cases: name -> (cmd, asserts)
# ============================================================
CASES = {
    # ---- G2/G3: partial mapping - mapping fixed + auto selection ----
    # (pairing-summary "Protein: N pair(s)" asserted in G7_summary, step 7)
    "F1_partial_mapping": {
        "cmd": ["complexA.pdb", "complexB.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_A.txt", "-outfmt", "2"],
        "asserts": [
            ("mapping", [("A", "A"), ("B", "B"), ("C", "C")]),  # A fixed; B/C auto-selected to standard answer
        ],
    },
    "F2_two_mappings": {
        "cmd": ["complexA.pdb", "complexB.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_AB.txt", "-outfmt", "2"],
        "asserts": [
            ("mapping", [("A", "A"), ("B", "B"), ("C", "C")]),
        ],
    },
    # ---- G7: pairing summary format (step 7, needs change 14) ----
    "G7_summary": {
        "cmd": ["complexA.pdb", "complexB.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_AB.txt", "-outfmt", "2"],
        "asserts": [
            ("contains", "Chain pairing summary:"),
            ("contains", "Protein: 3 pair(s) aligned"),
            ("contains", "RNA: 0 pair(s) aligned"),
        ],
    },
    # ---- G6.1: duplicate target defense ----
    "F3_duplicate_target": {
        "cmd": ["complexA.pdb", "complexB.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_dup.txt", "-outfmt", "2"],
        "asserts": [
            ("contains", "already mapped as a target chain"),
        ],
    },
    # ---- G2.3: crossed mapping lock (4iaj A -> 4jhm B, even if auto would pick differently) ----
    # 4iaj/4jhm are copied into data/ by gen_constructed_data.py so output uses bare filenames
    "F4_lock_conflict": {
        "cmd": ["4iaj.pdb1", "4jhm.pdb1", "-mm", "1", "-ter", "0",
                "-chainmap", "map_4iaj_AtoB.txt", "-outfmt", "2"],
        "asserts": [
            ("mapping", [("A", "B")]),     # mapped pair A->B must appear first
        ],
    },
    # ---- G5.2: chain number mismatch ----
    "E1_chain_mismatch": {
        "cmd": ["complexA.pdb", "complexB_2chain.pdb", "-mm", "1", "-ter", "0", "-outfmt", "2"],
        "asserts": [
            ("contains", "Protein: 2 pair(s) aligned"),
            ("contains", "more chains in structure 1"),
        ],
    },
    # ---- G5.1: molecule type mismatch (auto) ----
    "E2_type_mismatch": {
        "cmd": [str(RNA_PDB), "complexA.pdb", "-mm", "1", "-ter", "0", "-outfmt", "2"],
        "asserts": [
            ("contains", "no chain of the same molecule type"),
        ],
    },
    # ---- G5.1: -mol protein pre-scan warning ----
    "E3_mol_prescan": {
        "cmd": [str(RNA_PDB), "complexA.pdb", "-mm", "1", "-ter", "0", "-mol", "protein", "-outfmt", "2"],
        "asserts": [
            ("contains", "will be filtered out"),
        ],
    },
    # ---- G6.3: type-mismatch mapping - warning + ignore ----
    "E4_mapping_type_mismatch": {
        "cmd": [str(RNA_PDB), "complexA.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_rna_type.txt", "-outfmt", "2"],
        "asserts": [
            ("contains", "molecule type mismatch"),
        ],
    },
    # ---- G6.4: nonexistent chain id in chainmap ----
    "B4_nonexistent_chain": {
        "cmd": ["complexA.pdb", "complexB.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_nonexist.txt", "-outfmt", "2"],
        "asserts": [
            ("contains", "Warning! Cannot map chain X of structure 1 to chain A of structure 2"),
            ("contains", "does not exist in structure 1"),
            ("contains", "no valid chain mapping found in map_nonexist.txt"),
            ("contains", "as if no -chainmap was specified"),
        ],
    },
    # ---- G8.3: partial mapping + chain mismatch ----
    "B2_mapping_plus_mismatch": {
        "cmd": ["complexA.pdb", "complexB_2chain.pdb", "-mm", "1", "-ter", "0",
                "-chainmap", "map_A.txt", "-outfmt", "2"],
        "asserts": [
            ("contains", "Protein: 2 pair(s) aligned"),
            ("contains", "more chains in structure 1"),
            ("mapping", [("A", "A")]),
        ],
    },
}


def main():
    selected = sys.argv[1:] if len(sys.argv) > 1 else list(CASES)
    if not EXE.exists():
        print("ERROR: test executable not found:", EXE)
        print("Run run_regression.py first (it compiles the executable).")
        sys.exit(1)

    total = passed = failed = 0
    for name in selected:
        if name not in CASES:
            print(f"SKIP unknown case: {name}")
            continue
        case = CASES[name]
        print(f"=== {name} ===")
        print("  CMD:", " ".join(case["cmd"]))
        proc = run_case(case, name)
        failures = check_asserts(name, proc, case["asserts"])
        total += 1
        if failures:
            failed += 1
            for f in failures:
                print("  FAIL:", f)
        else:
            passed += 1
            print("  PASS")
    print(f"\n===== Feature summary: {passed} passed, {failed} failed (total {total}) =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
