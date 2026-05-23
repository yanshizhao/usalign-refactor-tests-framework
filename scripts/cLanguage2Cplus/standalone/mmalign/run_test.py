#!/usr/bin/env python3
"""
MMalign 回归测试脚本
编译当前源码（USalign-beta）的 MMalign，运行全部用例，与 baseline/ 逐字节比对。
生成文件: -o complex1.sup 会产生 complex1.sup / *.pml; -m matrix.txt 会产生 matrix.txt
"""
import subprocess, shutil, sys, difflib, re
from pathlib import Path


def strip_cpu_time(text: str) -> str:
    """移除 #Total CPU time 行 — CPU 时间自然波动，不作为回归判定依据"""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = USALIGN_DIR / "MMalign.cpp"
EXE_NAME     = "MMalign_mod.exe"


def compile_mod(exe_path: str):
    print("Compiling modified MMalign ...")
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static", "-o", exe_path, str(SRC_MAIN)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


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
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args = args_str.split()
            cmd = [exe_path] + args

            print(f"=== {name} ===", end=" ")

            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr

            cur_file = CURRENT_DIR / f"{name}.out"
            cur_file.write_text(content, encoding="utf-8")

            base_file = BASELINE_DIR / f"{name}.out"
            if not base_file.exists():
                print("FAIL (no baseline)")
                total_fail += 1
                continue

            base_content = base_file.read_text(encoding="utf-8")
            content = strip_cpu_time(content)
            base_content = strip_cpu_time(base_content)
            if content == base_content:
                print("PASS")
                total_pass += 1
            else:
                print("FAIL")
                total_fail += 1
                diff_file = DIFFS_DIR / f"{name}.diff"
                with open(diff_file, "w", encoding="utf-8") as df:
                    df.writelines(difflib.unified_diff(
                        base_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"baseline/{name}.out",
                        tofile=f"current/{name}.out"))

            # 比对 -o complex1.sup 生成的叠合文件
            sup_path = workdir / "complex1.sup"
            base_sup = BASELINE_DIR / f"{name}.sup"
            if sup_path.exists():
                shutil.copy2(str(sup_path), str(CURRENT_DIR / f"{name}.sup"))
            if sup_path.exists() and base_sup.exists():
                if sup_path.read_bytes() == base_sup.read_bytes():
                    print(f"  complex1.sup: PASS")
                    total_pass += 1
                else:
                    print(f"  complex1.sup: FAIL")
                    total_fail += 1
                sup_path.unlink()
            elif sup_path.exists():
                sup_path.unlink()

            # 比对 -m matrix.txt 生成的矩阵文件
            matrix_path = workdir / "matrix.txt"
            base_matrix = BASELINE_DIR / f"{name}.matrix.txt"
            if matrix_path.exists():
                shutil.copy2(str(matrix_path), str(CURRENT_DIR / f"{name}.matrix.txt"))
            if matrix_path.exists() and base_matrix.exists():
                if matrix_path.read_bytes() == base_matrix.read_bytes():
                    print(f"  matrix.txt: PASS")
                    total_pass += 1
                else:
                    print(f"  matrix.txt: FAIL")
                    total_fail += 1
                matrix_path.unlink()
            elif matrix_path.exists():
                matrix_path.unlink()

            # 清理 pml
            for pml in workdir.glob("*.pml"):
                pml.unlink()

    print(f"\nResults: {total_pass} PASS, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    exe = str(SCRIPT_DIR / EXE_NAME)
    compile_mod(exe)
    ok = run_tests(exe)
    sys.exit(0 if ok else 1)
