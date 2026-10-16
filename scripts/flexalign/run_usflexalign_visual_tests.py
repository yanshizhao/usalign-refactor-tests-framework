#!/usr/bin/env python3
"""
Independent CLI visual-content tests for USFlexalign.

Calls the beta USFlexalign.exe entry point directly (not through the -mm 7
regression runner) and asserts the *content* of the PyMOL / RasMol / ChimeraX
products, for both a chain-less and a chained input pair.

Exit code: 0 = all cases pass, non-zero = failure (1) or precondition (2).
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
NOCHAIN_DIR = DATA_DIR / "3icyA-3lyxA"

# __file__ = .../usalign-refactor-tests-framework/scripts/flexalign/<this>.py
# parent x4 = us-align_modify/
USALIGN_DIR = SCRIPT_DIR.parent.parent.parent / "USalign"
MASTER_DIR = USALIGN_DIR.parent.parent / "_master_viz_fix"

EXE_SUFFIX = ".exe" if os.name == "nt" else ""
EXE = USALIGN_DIR / f"USFlexalign{EXE_SUFFIX}"

PREFIX = "sup"
RASMOL_EXT = ".spt"
PYMOL_EXT = ".pml"
CHIMERAX_EXT = ".cxc"
VARIANTS = ["", "_all", "_atm", "_all_atm", "_all_atm_lig"]

NOCHAIN_PDBS = [NOCHAIN_DIR / "3icyA.pdb", NOCHAIN_DIR / "3lyxA.pdb"]
CHAIN_PDBS = [MASTER_DIR / "PDB2.pdb", MASTER_DIR / "PDB1.pdb"]

SEGMENT_SELECT = re.compile(r"^select\s+[\d,\s:A-Z]+$")
SEGMENT_COLOR = re.compile(r"^color\s+(\S+)")


def clean_env():
    """Drop /mingw64/bin from PATH (wrong libstdc++-6.dll would break the run)."""
    env = dict(os.environ)
    entries = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(e for e in entries if "mingw64" not in e)
    return env


def run_usflexalign(pdbs, option, workdir):
    cmd = [str(EXE)]
    cmd.extend(str(p) for p in pdbs)
    cmd.extend([option, PREFIX, "-outdir", "."])
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(workdir), env=clean_env())
    return proc.returncode, proc.stdout + proc.stderr


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def product(workdir, variant, ext):
    return workdir / f"{PREFIX}{variant}{ext}"


def segment_colors(text):
    """Pair each chain-less numeric 'select' line with the color command after it."""
    lines = text.splitlines()
    pairs = []
    for i, line in enumerate(lines):
        if SEGMENT_SELECT.match(line):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            match = SEGMENT_COLOR.match(nxt)
            pairs.append((line, match.group(1) if match else None))
    return pairs


def check_nochain_rasmol(workdir):
    fails = []
    for variant in VARIANTS:
        path = product(workdir, variant, RASMOL_EXT)
        if not path.exists():
            fails.append(f"missing product: {path.name}")
            continue
        text = read_text(path)
        if "ATOM" not in text:
            fails.append(f"{path.name}: no ATOM records")
        if re.search(r"^color white", text, re.M):
            fails.append(f"{path.name}: contains 'color white'")
        pairs = segment_colors(text)
        if len(pairs) != 3:
            fails.append(f"{path.name}: expected 3 segment selections, got {len(pairs)}")
        for select_line, color in pairs:
            if ":" in select_line:
                fails.append(f"{path.name}: chain-less segment carries a chain suffix: {select_line[:40]}")
            if color is None:
                fails.append(f"{path.name}: segment selection without a color command: {select_line[:40]}")
        if "_atm" not in variant and not re.search(r"^color grey", text, re.M):
            fails.append(f"{path.name}: missing CA base color 'color grey'")
    return fails


def check_nochain_pymol(workdir):
    fails = []
    for variant in VARIANTS:
        path = product(workdir, variant, PYMOL_EXT)
        if not path.exists():
            fails.append(f"missing product: {path.name}")
            continue
        text = read_text(path)
        if "select hinge_" not in text:
            fails.append(f"{path.name}: missing 'select hinge_'")
        if "color wheat, structure2" not in text:
            fails.append(f"{path.name}: missing 'color wheat, structure2'")
        if "color white, structure2" in text:
            fails.append(f"{path.name}: contains 'color white, structure2'")
    return fails


def check_nochain_chimerax(workdir):
    fails = []
    for variant in VARIANTS:
        path = product(workdir, variant, CHIMERAX_EXT)
        if not path.exists():
            fails.append(f"missing product: {path.name}")
            continue
        text = read_text(path)
        if "#!/usr/bin/env chimerax --script" not in text:
            fails.append(f"{path.name}: missing chimerax shebang")
        if f'open "{PREFIX}_structure2.pdb" name structure2' not in text:
            fails.append(f"{path.name}: missing structure2 open line")
        if "color #2 wheat" not in text:
            fails.append(f"{path.name}: missing 'color #2 wheat'")
        if "color #2 white" in text:
            fails.append(f"{path.name}: contains 'color #2 white'")
        seg_colors = re.findall(r"^color #1:[\d,]+ \S+", text, re.M)
        if len(seg_colors) != 3:
            fails.append(f"{path.name}: expected 3 per-segment '#1' colors, got {len(seg_colors)}")
    return fails


def check_chain_rasmol(workdir):
    fails = []
    for variant in VARIANTS:
        path = product(workdir, variant, RASMOL_EXT)
        if not path.exists():
            fails.append(f"missing product: {path.name}")
            continue
        text = read_text(path)
        if "ATOM" not in text:
            fails.append(f"{path.name}: no ATOM records")
        selects = [l for l in text.splitlines() if SEGMENT_SELECT.match(l)]
        if len(selects) != 2:
            fails.append(f"{path.name}: expected 2 segment selections, got {len(selects)}")
        if not re.search(r"^select\s+[\d,]+:A", text, re.M):
            fails.append(f"{path.name}: segment selection lacks ':A' chain suffix")
    return fails


CASES = [
    ("nochain_rasmol", NOCHAIN_PDBS, "-rasmol", check_nochain_rasmol),
    ("nochain_pymol", NOCHAIN_PDBS, "-pymol", check_nochain_pymol),
    ("nochain_chimerax", NOCHAIN_PDBS, "-chimerax", check_nochain_chimerax),
    ("chain_rasmol", CHAIN_PDBS, "-rasmol", check_chain_rasmol),
]


def main():
    if not EXE.exists():
        print(f"ERROR: executable not found: {EXE}")
        print("Build it first: cd USalign && mingw32-make USFlexalign")
        return 2
    missing = [p for _, pdbs, _, _ in CASES for p in pdbs if not p.exists()]
    if missing:
        print("ERROR: test input missing: " + ", ".join(str(p) for p in missing))
        return 2

    total = passed = 0
    with tempfile.TemporaryDirectory(prefix="usflexalign_visual_") as tmp:
        for name, pdbs, option, checker in CASES:
            workdir = Path(tmp) / name
            workdir.mkdir(parents=True, exist_ok=True)
            print(f"\n=== {name} ===")
            rc, output = run_usflexalign(pdbs, option, workdir)
            fails = checker(workdir) if rc == 0 else [f"USFlexalign exit code {rc}"]
            total += 1
            if fails:
                print(f"  FAIL")
                for msg in fails:
                    print(f"    - {msg}")
                tail = [l for l in output.splitlines() if l.strip()][-3:]
                for line in tail:
                    print(f"    | {line}")
            else:
                print("  PASS")
                passed += 1

    failed = total - passed
    print(f"\n===== Summary: total={total}, PASS={passed}, FAIL={failed} =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
