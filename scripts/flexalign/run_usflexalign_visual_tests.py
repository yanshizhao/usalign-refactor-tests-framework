#!/usr/bin/env python3
"""
Independent CLI visual-content tests for USFlexalign.

Calls the USFlexalign / USalign entry points directly (not through the -mm 7
regression runner) and asserts the *content* of the PyMOL / RasMol / ChimeraX
products, for both a chain-less and a chained input pair.

Exit code: 0 = all cases pass, non-zero = failure (1) or precondition (2).
"""
import argparse
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

EXE_SUFFIX = ".exe" if os.name == "nt" else ""
EXE_NAMES = {
    "uf": f"USFlexalign{EXE_SUFFIX}",
    "mm7": f"USalign{EXE_SUFFIX}",
}

PREFIX = "sup"
RASMOL_EXT = ".spt"
PYMOL_EXT = ".pml"
CHIMERAX_EXT = ".cxc"
VARIANTS = ["", "_all", "_atm", "_all_atm", "_all_atm_lig"]

NOCHAIN_PDBS = [NOCHAIN_DIR / "3icyA.pdb", NOCHAIN_DIR / "3lyxA.pdb"]
CHAIN_PDBS = [DATA_DIR / "US185232304A.pdb", DATA_DIR / "US185232304B.pdb"]

SEGMENT_SELECT = re.compile(r"^select\s+[\d,\s:A-Z]+$")
SEGMENT_COLOR = re.compile(r"^color\s+(\S+)\s*$")
# Base (structure1/structure2) colors written in the RasMol headers.
BASE_COLORS = ("grey", "yellowtint")
# RasMol refuses a script line longer than 256 chars; the writer caps at 250.
MAX_LINE_LEN = 250


def clean_env():
    """Drop /mingw64/bin from PATH (wrong libstdc++-6.dll would break the run)."""
    env = dict(os.environ)
    entries = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(e for e in entries if "mingw64" not in e)
    return env


def run_entry(exe, pdbs, option_flags, workdir):
    """Run one tool through one entry point, products written into workdir.

    The CLI differs between builds: the USalign main program needs '-mm 7' plus the
    tool flag, accepts '-outdir .' only in beta and spells PyMOL as '-o' there
    (the older master CLI accepts neither). Try the arg forms in order.
    """
    base = [str(exe)]
    base.extend(str(p) for p in pdbs)
    ok = None
    for flags in option_flags:
        for extra in (["-outdir", "."], []):
            cmd = base + flags + [PREFIX] + extra
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  cwd=str(workdir), env=clean_env())
            ok = (proc.returncode, proc.stdout + proc.stderr)
            # Only stop once products actually landed in workdir: a successful
            # exit without '-outdir' writes to the default results/ dir instead.
            if proc.returncode == 0 and any(workdir.glob(f"{PREFIX}*")):
                return ok
    return ok


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def product(workdir, variant, ext):
    return workdir / f"{PREFIX}{variant}{ext}"


def segment_colors(text):
    """Pair each numeric 'select' line (one segment chunk) with the color after it.

    A segment whose residue list does not fit on one command line is split into
    several 'select' chunks, each followed by the same color, so the number of
    pairs can exceed the number of segments.
    """
    lines = text.splitlines()
    pairs = []
    for i, line in enumerate(lines):
        if SEGMENT_SELECT.match(line):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            match = SEGMENT_COLOR.match(nxt)
            pairs.append((line, match.group(1) if match else None))
    return pairs


def collapse_runs(colors):
    """Collapse consecutive duplicates (split chunks repeat their segment color)."""
    runs = []
    for color in colors:
        if not runs or runs[-1] != color:
            runs.append(color)
    return runs


def overlong_line(text):
    for line in text.splitlines():
        if len(line) > MAX_LINE_LEN:
            return line
    return None


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
        if re.search(r"^color white\s*$", text, re.M):
            fails.append(f"{path.name}: contains 'color white'")
        long_line = overlong_line(text)
        if long_line is not None:
            fails.append(f"{path.name}: found a line of {len(long_line)} chars (> {MAX_LINE_LEN})")
        for base in BASE_COLORS:
            if not re.search(rf"^color {base}\s*$", text, re.M):
                fails.append(f"{path.name}: missing base color 'color {base}'")
        pairs = segment_colors(text)
        for select_line, color in pairs:
            if not re.search(r"\d+:A", select_line):
                fails.append(f"{path.name}: segment selection lacks ':A' chain suffix: {select_line[:40]}")
            if color is None:
                fails.append(f"{path.name}: segment selection without a color command: {select_line[:40]}")
        runs = collapse_runs([c for _s, c in pairs])
        if runs != ["blue", "red", "green"]:
            fails.append(f"{path.name}: expected segment colors [blue, red, green], got {runs}")
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
        long_line = overlong_line(text)
        if long_line is not None:
            fails.append(f"{path.name}: found a line of {len(long_line)} chars (> {MAX_LINE_LEN})")
        for base in BASE_COLORS:
            if not re.search(rf"^color {base}\s*$", text, re.M):
                fails.append(f"{path.name}: missing base color 'color {base}'")
        pairs = segment_colors(text)
        if not pairs:
            fails.append(f"{path.name}: no segment selections found")
        for select_line, color in pairs:
            if not re.search(r"\d+:A", select_line):
                fails.append(f"{path.name}: segment selection lacks ':A' chain suffix: {select_line[:40]}")
            if color is None:
                fails.append(f"{path.name}: segment selection without a color command: {select_line[:40]}")
        runs = collapse_runs([c for _s, c in pairs])
        if runs != ["blue", "red"]:
            fails.append(f"{path.name}: expected segment colors [blue, red], got {runs}")
    return fails


MM7 = ["-mm", "7"]
PYMOL_UF = [["-pymol"], ["-o"]]
PYMOL_MM7 = [MM7 + ["-pymol"], MM7 + ["-o"]]
RASMOL_UF = [["-rasmol"]]
RASMOL_MM7 = [MM7 + ["-rasmol"]]
CHIMERAX_UF = [["-chimerax"]]
CHIMERAX_MM7 = [MM7 + ["-chimerax"]]

CASES = [
    ("nochain_rasmol_uf", NOCHAIN_PDBS, "uf", RASMOL_UF, check_nochain_rasmol),
    ("nochain_rasmol_mm7", NOCHAIN_PDBS, "mm7", RASMOL_MM7, check_nochain_rasmol),
    ("nochain_pymol_uf", NOCHAIN_PDBS, "uf", PYMOL_UF, check_nochain_pymol),
    ("nochain_pymol_mm7", NOCHAIN_PDBS, "mm7", PYMOL_MM7, check_nochain_pymol),
    ("nochain_chimerax_uf", NOCHAIN_PDBS, "uf", CHIMERAX_UF, check_nochain_chimerax),
    ("nochain_chimerax_mm7", NOCHAIN_PDBS, "mm7", CHIMERAX_MM7, check_nochain_chimerax),
    ("chain_rasmol_uf", CHAIN_PDBS, "uf", RASMOL_UF, check_chain_rasmol),
    ("chain_rasmol_mm7", CHAIN_PDBS, "mm7", RASMOL_MM7, check_chain_rasmol),
]


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe-dir",
        default=str(USALIGN_DIR),
        help="directory containing USFlexalign / USalign executables (default: beta build)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    exe_dir = Path(args.exe_dir).resolve()
    exes = {key: exe_dir / name for key, name in EXE_NAMES.items()}
    missing_exe = [str(e) for e in exes.values() if not e.exists()]
    if missing_exe:
        print("ERROR: executable not found: " + ", ".join(missing_exe))
        print("Build first: cd USalign && mingw32-make USFlexalign USalign")
        return 2
    missing = [p for _, pdbs, _, _, _ in CASES for p in pdbs if not p.exists()]
    if missing:
        print("ERROR: test input missing: " + ", ".join(str(p) for p in missing))
        return 2

    total = passed = 0
    with tempfile.TemporaryDirectory(prefix="usflexalign_visual_") as tmp:
        for name, pdbs, exe_key, flags, checker in CASES:
            workdir = Path(tmp) / name
            workdir.mkdir(parents=True, exist_ok=True)
            print(f"\n=== {name} ===")
            rc, output = run_entry(exes[exe_key], pdbs, flags, workdir)
            fails = checker(workdir) if rc == 0 else [f"entry exit code {rc}"]
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
