"""Shared utilities for USalign regression scripts.

Used by run_regression.py (and reusable by other sub-flows such as
chainmap_local) for output normalization, CPU-time filtering and
baseline/current comparison.
"""

import shutil, difflib, re
from pathlib import Path


def clean_directory(dir_path):
    """Remove and recreate a directory (fresh state for each run)."""
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
    return re.sub(r'^\s*#Total CPU time.*\n?', '', text, flags=re.MULTILINE)


def is_non_business_line(line: str) -> bool:
    """Determine whether a diff line is non-business content (CPU time, etc., environmental differences)"""
    stripped = line.strip()
    if not stripped:
        return True
    if "#Total CPU time is" in stripped:
        return True
    return False


def diff_files(base_filename, mod_filename, tag, baseline_dir, current_dir, diffs_dir, extra_note=""):
    """Compare text output files with CPU-time-aware classification.

    Returns: "PASS" (identical), "WARNING" (only CPU time differs), "FAIL" (business data differs)
    """
    base = baseline_dir / base_filename
    curr = current_dir / mod_filename
    diff = diffs_dir / f"{tag}.diff"
    try:
        btext = clean_slash(strip_cpu_time(base.read_text(encoding="utf-8", errors="replace")))
        ctext = clean_slash(strip_cpu_time(curr.read_text(encoding="utf-8", errors="replace")))
        if btext == ctext:
            print(f"  PASS{extra_note}")
            if diff.exists():
                diff.unlink()
            return "PASS"

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


def diff_binary(base_filename, mod_filename, tag, baseline_dir, current_dir, diffs_dir, extra_note=""):
    """Byte-level comparison for structure files (.pdb, .sup).

    Returns: "PASS" (identical) or "FAIL" (any byte difference)
    """
    base = baseline_dir / base_filename
    curr = current_dir / mod_filename
    diff = diffs_dir / f"{tag}.diff"
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
